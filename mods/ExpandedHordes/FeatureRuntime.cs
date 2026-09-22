using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.CompilerServices;
using HarmonyLib;

namespace ExpandedHordes
{
    internal enum Feature { Population, Catalog, Composition, Attraction, Movement, Resistance, Corpses, Diagnostics, Profiling }

    // Patch ownership is per feature. A failed optional hook does not disable the horde.
    internal static class FeatureRuntime
    {
        private static readonly Dictionary<Feature, Harmony> Installed = new Dictionary<Feature, Harmony>();
        private static readonly HashSet<Feature> Failed = new HashSet<Feature>();
        private static readonly HashSet<string> Warnings = new HashSet<string>();

        internal static void WarnOnce(string key, string message)
        {
            if (Warnings.Add(key)) Plugin.Log.LogWarning(message);
        }

        internal static bool Enabled(Feature feature) => !Failed.Contains(feature);

        internal static void InstallProfiler() => Install(Feature.Profiling,
            typeof(ProfileZombieUpdate), typeof(ProfileCorpseCreation), typeof(ProfilePlacement), typeof(ProfileHordeSave));

        internal static void Install(Feature feature, params Type[] patches)
        {
            if (Installed.ContainsKey(feature)) return;
            var harmony = new Harmony(ModIdentity.Guid + "." + feature.ToString().ToLowerInvariant());
            try
            {
                foreach (Type patch in patches)
                {
                    RuntimeHelpers.RunClassConstructor(patch.TypeHandle);
                    harmony.CreateClassProcessor(patch).Patch();
                }
                Installed.Add(feature, harmony);
                DebugLog($"Enabled {feature} ({patches.Length} patch classes).");
                if (ModSettings.DebugMode.Value)
                    foreach (var method in harmony.GetPatchedMethods())
                    {
                        var owners = Harmony.GetPatchInfo(method)?.Owners.Where(o => !o.StartsWith(ModIdentity.Guid, StringComparison.Ordinal));
                        if (owners != null && owners.Any()) DebugLog($"Shared hook {method.DeclaringType?.Name}.{method.Name}; other owners: {string.Join(", ", owners)}. This is overlap, not proof of conflict.");
                    }
            }
            catch (Exception ex)
            {
                try { harmony.UnpatchSelf(); }
                catch (Exception rollback) { Plugin.Log.LogError($"Could not roll back {feature} patches: {rollback}"); }
                Fail(feature, ex);
            }
        }

        internal static void Fail(Feature feature, Exception error)
        {
            if (Failed.Add(feature))
            {
                Plugin.Log.LogError($"{feature} disabled for this session; native behavior is retained where possible. {error}");
                if (feature == Feature.Population)
                {
                    try { PopulationOverrides.Restore(); }
                    catch (Exception restore) { Plugin.Log.LogError("Could not restore owned population values: " + restore); }
                }
            }
        }

        internal static void DebugLog(string message)
        {
            if (ModSettings.DebugMode.Value) Plugin.Log.LogInfo("[debug] " + message);
        }

        internal static void Stop()
        {
            foreach (var patch in Installed.Values)
            {
                try { patch.UnpatchSelf(); }
                catch (Exception ex) { Plugin.Log.LogError($"Could not remove owned patches {patch.Id}: {ex}"); }
            }
            Installed.Clear();
            Failed.Clear();
            Warnings.Clear();
        }
    }
}
