using System.IO;
using System;
using BepInEx;
using BepInEx.Logging;
using UnityEngine;

namespace ExpandedHordes
{
    [BepInPlugin(Guid, ModIdentity.Name, Version)]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string Guid = ModIdentity.Guid;
        public const string Version = ModIdentity.Version;
        internal static ManualLogSource Log;

        private void Awake()
        {
            Log = Logger;
            ModSettings.Bind(Config);
            FeatureRuntime.Install(Feature.Population, typeof(AiSetup), typeof(HordeAllowance), typeof(SpawnBudget));
            FeatureRuntime.Install(Feature.Catalog, typeof(HordeSetup));
            if (FeatureRuntime.Enabled(Feature.Catalog))
            {
                FeatureRuntime.Install(Feature.Composition, typeof(HordeComposition));
                FeatureRuntime.Install(Feature.Resistance, typeof(DamageResistance));
            }
            FeatureRuntime.Install(Feature.Attraction, typeof(HordeStart));
            FeatureRuntime.Install(Feature.Movement, typeof(HordeRunSpeed));
            FeatureRuntime.Install(Feature.Corpses, typeof(CorpseRetention));
            if (ModSettings.DebugMode.Value)
                FeatureRuntime.Install(Feature.Diagnostics, typeof(PlacementResult), typeof(ContextResult), typeof(PlacementSummary));
            if (ModSettings.Profiling.Value)
            {
                FeatureRuntime.InstallProfiler();
                PerformanceMonitor.Start(Path.GetDirectoryName(Info.Location));
            }
            Log.LogInfo($"Expanded Hordes {Version} loaded | game {Application.version} | base budget {ModSettings.Total.Value}, living {ModSettings.Living.Value}, shared AI {ModSettings.Allowance.Value}, run speed {ModSettings.RunSpeedPercent.Value}%; resistance regular/large/boss {ModSettings.RegularResistance.Value}/{ModSettings.LargeResistance.Value}/{ModSettings.BossResistance.Value}%; corpse target {ModSettings.CorpseLimit.Value}. Restart after configuration changes.");
        }

        private void Update() => PerformanceMonitor.Update();

        private void OnDestroy()
        {
            PlacementLog.Flush();
            PerformanceMonitor.Stop();
            try { PopulationOverrides.Restore(); }
            catch (Exception ex) { Log.LogError("Could not restore owned population values: " + ex); }
            finally { FeatureRuntime.Stop(); CreatureCatalog.Clear(); }
        }
    }
}
