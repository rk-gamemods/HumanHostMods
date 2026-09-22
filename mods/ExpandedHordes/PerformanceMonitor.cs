using System;
using System.Collections;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using HarmonyLib;
using UnityEngine;

namespace ExpandedHordes
{
    internal enum ProfileSection { ZombieUpdate, Placement, CorpseCreation, HordeSave, Resistance, RunSpeed, Composition, Count }

    internal static class PerformanceMonitor
    {
        private const float Interval = 15f;
        private const long MaxCsvBytes = 5 * 1024 * 1024;
        private static readonly FrameWindow Frames = new FrameWindow();
        private static readonly FrameTiming[] Timing = new FrameTiming[1];
        private static readonly long[] Counts = new long[(int)ProfileSection.Count];
        private static readonly long[] Ticks = new long[(int)ProfileSection.Count];
        private static readonly long[] MaxTicks = new long[(int)ProfileSection.Count];
        private static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;
        private static readonly FieldInfo Alive = AccessTools.Field(typeof(NPC_Horde_Mgr), "_aliveHordeNPCs");
        private static readonly FieldInfo Bodies = AccessTools.Field(typeof(GPUI_Dead_Body_Mgr), "_ActiveDeadBodies");
        private static bool active, csvEnabled, timingAvailable;
        private static string csvPath;
        private static float lastReport;
        private static ulong lastTimestamp;
        private static int mainCount, renderCount, gpuCount, waitCount, lastGc;
        private static double mainMs, renderMs, gpuMs, waitMs;

        internal static bool Active => active && FeatureRuntime.Enabled(Feature.Profiling);
        internal static long Begin() => Active ? Stopwatch.GetTimestamp() : 0;
        internal static void End(ProfileSection section, long started)
        {
            if (started == 0 || !Active) return;
            long elapsed = Math.Max(0, Stopwatch.GetTimestamp() - started);
            int index = (int)section;
            Counts[index]++; Ticks[index] += elapsed; MaxTicks[index] = Math.Max(MaxTicks[index], elapsed);
        }

        internal static void Start(string directory)
        {
            if (active || !ModSettings.Profiling.Value || !FeatureRuntime.Enabled(Feature.Profiling)) return;
            csvPath = Path.Combine(directory, "performance.csv");
            csvEnabled = timingAvailable = active = true;
            lastReport = Time.realtimeSinceStartup;
            lastGc = GC.CollectionCount(0);
            Reset();
            Plugin.Log.LogInfo("Performance profiling enabled: 15-second aggregates; timings include measurement overhead. CPU/GPU hints are not causal diagnoses.");
        }

        internal static void Update()
        {
            if (!Active) return;
            try
            {
                Frames.Add(Time.unscaledDeltaTime * 1000d);
                if (timingAvailable)
                {
                    try
                    {
                        FrameTimingManager.CaptureFrameTimings();
                        if (FrameTimingManager.GetLatestTimings(1, Timing) > 0 && Timing[0].frameStartTimestamp != lastTimestamp)
                        {
                            var t = Timing[0]; lastTimestamp = t.frameStartTimestamp;
                            if (Valid(t.cpuMainThreadFrameTime))
                            {
                                mainCount++; mainMs += t.cpuMainThreadFrameTime;
                                if (t.cpuMainThreadPresentWaitTime >= 0 && !double.IsInfinity(t.cpuMainThreadPresentWaitTime))
                                { waitCount++; waitMs += t.cpuMainThreadPresentWaitTime; }
                            }
                            if (Valid(t.cpuRenderThreadFrameTime)) { renderCount++; renderMs += t.cpuRenderThreadFrameTime; }
                            if (Valid(t.gpuFrameTime)) { gpuCount++; gpuMs += t.gpuFrameTime; }
                        }
                    }
                    catch (Exception ex)
                    {
                        timingAvailable = false;
                        FeatureRuntime.WarnOnce("frame-timings", "Unity frame timings unavailable; FPS and method profiling continue. " + ex.Message);
                    }
                }
                if (Time.realtimeSinceStartup - lastReport >= Interval) Report();
            }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Profiling, ex); active = false; }
        }

        private static bool Valid(double value) => value > 0 && !double.IsInfinity(value);
        private static string Number(double value) => value.ToString("F3", Invariant);
        private static string Average(double total, int count) => count == 0 ? "unavailable" : Number(total / count);
        private static int ReadCount(FieldInfo field, object owner) => owner == null || field == null ? -1 : (field.GetValue(owner) as ICollection)?.Count ?? -1;

        private static void Report()
        {
            if (Frames.Count == 0) return;
            double cpu = Math.Max(mainCount == 0 ? 0 : mainMs / mainCount, renderCount == 0 ? 0 : renderMs / renderCount);
            double gpu = gpuCount == 0 ? 0 : gpuMs / gpuCount;
            string hint = PerformanceRules.Hint(cpu, gpu, waitCount == 0 ? 0 : waitMs / waitCount, Frames.Mean);
            int gc = GC.CollectionCount(0), collections = Math.Max(0, gc - lastGc); lastGc = gc;
            int living = ReadCount(Alive, NPC_Horde_Mgr.ins), bodies = ReadCount(Bodies, GPUI_Dead_Body_Mgr.ins);
            double memory = GC.GetTotalMemory(false) / (1024d * 1024d);
            var row = new StringBuilder(DateTime.UtcNow.ToString("O", Invariant));
            row.Append(',').Append(Frames.Count).Append(',').Append(Frames.SampleCount)
                .Append(',').Append(Number(1000d / Frames.Mean)).Append(',').Append(Number(Frames.Mean))
                .Append(',').Append(Number(Frames.Percentile95())).Append(',').Append(Number(Frames.Maximum))
                .Append(',').Append(Average(mainMs, mainCount)).Append(',').Append(Average(renderMs, renderCount))
                .Append(',').Append(Average(gpuMs, gpuCount)).Append(',').Append(Average(waitMs, waitCount))
                .Append(',').Append(mainCount).Append(',').Append(renderCount).Append(',').Append(gpuCount).Append(',').Append(waitCount).Append(',').Append(hint)
                .Append(',').Append(Number(memory)).Append(',').Append(collections).Append(',').Append(living).Append(',').Append(bodies);
            var sections = new StringBuilder();
            for (int i = 0; i < Counts.Length; i++)
            {
                double total = Ticks[i] * 1000d / Stopwatch.Frequency;
                double max = MaxTicks[i] * 1000d / Stopwatch.Frequency;
                row.Append(',').Append(Counts[i]).Append(',').Append(Number(total)).Append(',').Append(Number(max));
                if (Counts[i] > 0) sections.Append($" {(ProfileSection)i}={Number(total)}ms/{Counts[i]}calls max={Number(max)}ms;");
            }
            Plugin.Log.LogInfo($"[profile] FPS={Number(1000d / Frames.Mean)} frame avg/p95/max={Number(Frames.Mean)}/{Number(Frames.Percentile95())}/{Number(Frames.Maximum)}ms CPU main/render={Average(mainMs, mainCount)}/{Average(renderMs, renderCount)}ms GPU={Average(gpuMs, gpuCount)}ms hint={hint}; horde living={living}, settled corpses={bodies}, managed={Number(memory)}MiB, gen0 GC={collections}; measured inclusive method totals:{sections}");
            WriteCsv(row.ToString());
            Reset(); lastReport = Time.realtimeSinceStartup;
        }

        private static void WriteCsv(string row)
        {
            if (!csvEnabled) return;
            try
            {
                if (File.Exists(csvPath) && new FileInfo(csvPath).Length >= MaxCsvBytes)
                {
                    string previous = Path.Combine(Path.GetDirectoryName(csvPath), "performance.previous.csv");
                    if (File.Exists(previous)) File.Delete(previous);
                    File.Move(csvPath, previous);
                }
                if (!File.Exists(csvPath))
                {
                    var header = new StringBuilder("utc,frames,percentile_samples,fps,frame_mean_ms,frame_p95_ms,frame_max_ms,cpu_main_ms,cpu_render_ms,gpu_ms,present_wait_ms,cpu_main_samples,cpu_render_samples,gpu_samples,present_wait_samples,hint,managed_mib,gc_gen0,horde_living,settled_corpses");
                    for (int i = 0; i < Counts.Length; i++) header.Append($",{(ProfileSection)i}_calls,{(ProfileSection)i}_total_ms,{(ProfileSection)i}_max_ms");
                    File.WriteAllText(csvPath, header + Environment.NewLine);
                }
                File.AppendAllText(csvPath, row + Environment.NewLine);
            }
            catch (Exception ex) { csvEnabled = false; FeatureRuntime.WarnOnce("profile-csv", "Profiling CSV disabled; log summaries continue. " + ex.Message); }
        }

        private static void Reset()
        {
            Frames.Reset(); mainCount = renderCount = gpuCount = waitCount = 0; mainMs = renderMs = gpuMs = waitMs = 0;
            Array.Clear(Counts, 0, Counts.Length); Array.Clear(Ticks, 0, Ticks.Length); Array.Clear(MaxTicks, 0, MaxTicks.Length);
        }
        internal static void Stop() { active = false; Reset(); lastTimestamp = 0; }
    }

    [HarmonyPatch(typeof(Zombie_Agent), "_Update")]
    internal static class ProfileZombieUpdate
    {
        private static void Prefix(out long __state) => __state = PerformanceMonitor.Begin();
        private static Exception Finalizer(Exception __exception, long __state)
        { PerformanceMonitor.End(ProfileSection.ZombieUpdate, __state); return __exception; }
    }
    [HarmonyPatch(typeof(GPUI_Dead_Body_Mgr), "Spawn_GPUI_Dead_Body")]
    internal static class ProfileCorpseCreation
    {
        private static void Prefix(out long __state) => __state = PerformanceMonitor.Begin();
        private static Exception Finalizer(Exception __exception, long __state)
        { PerformanceMonitor.End(ProfileSection.CorpseCreation, __state); return __exception; }
    }
    [HarmonyPatch(typeof(NPC_Horde_Mgr), "GetValidSpawnPosition")]
    internal static class ProfilePlacement
    {
        private static void Prefix(out long __state) => __state = PerformanceMonitor.Begin();
        private static Exception Finalizer(Exception __exception, long __state)
        { PerformanceMonitor.End(ProfileSection.Placement, __state); return __exception; }
    }
    [HarmonyPatch(typeof(NPC_Horde_Mgr), "Save_Horde_Data_To_Disk")]
    internal static class ProfileHordeSave
    {
        private static void Prefix(out long __state) => __state = PerformanceMonitor.Begin();
        private static Exception Finalizer(Exception __exception, long __state)
        { PerformanceMonitor.End(ProfileSection.HordeSave, __state); return __exception; }
    }
}
