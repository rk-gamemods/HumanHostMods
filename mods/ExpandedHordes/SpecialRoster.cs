using System;
using HarmonyLib;
using UnityEngine;
using Random = UnityEngine.Random;

namespace ExpandedHordes
{
    internal static class SpecialRoster
    {
        private static readonly AccessTools.FieldRef<Terrain_Loader_Manager, float> GridWidth =
            AccessTools.FieldRefAccess<Terrain_Loader_Manager, float>("BigTerraWidth");
        internal static void Select(ref int biome, ref int group, ref int prefab)
        {
            var loader = Terrain_Loader_Manager.ins;
            Vector3 real = Player_Input.ins.transform.position - loader.neutralizedPlayerMove;
            int region = HordeRules.Region(real.x, real.z, GridWidth(loader), loader.BiomesWidthDis);
            int category = HordeRules.Category(Random.Range(0, 100), region, ModSettings.LargeBegin.Value,
                ModSettings.BossBegin.Value, ModSettings.LargePercent.Value, ModSettings.BossPercent.Value);
            if (category == 0) return;
            var pool = category == 2 ? CreatureCatalog.Bosses : CreatureCatalog.Large;
            if (pool.Count == 0) return;
            CreatureCatalog.Entry choice = pool[Random.Range(0, pool.Count)];
            biome = choice.Biome;
            group = choice.Group;
            prefab = choice.Prefab;
        }
    }

    [HarmonyPatch(typeof(NPC_Horde_Mgr), "Spawn_Horde_NPC")]
    internal static class HordeComposition
    {
        private static void Prefix(ref int biomeIndex, ref int groupIndex, ref int npcPrefabIndex, bool async)
        {
            if (!async || G_Save.isQuit || !FeatureRuntime.Enabled(Feature.Composition)) return;
            long started = PerformanceMonitor.Begin();
            try { SpecialRoster.Select(ref biomeIndex, ref groupIndex, ref npcPrefabIndex); }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Composition, ex); }
            finally { PerformanceMonitor.End(ProfileSection.Composition, started); }
        }
    }
}
