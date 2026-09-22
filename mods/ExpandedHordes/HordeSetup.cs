using System;
using HarmonyLib;

namespace ExpandedHordes
{
    [HarmonyPatch(typeof(NPC_Horde_Mgr), "_Start")]
    internal static class HordeSetup
    {
        private static void Prefix()
        {
            PlacementLog.Reset();
            if (!FeatureRuntime.Enabled(Feature.Catalog)) return;
            try { CreatureCatalog.Resolve(NPC_Spawner_Mgr.ins); }
            catch (Exception ex)
            {
                CreatureCatalog.Clear();
                FeatureRuntime.Fail(Feature.Catalog, ex);
                FeatureRuntime.Fail(Feature.Composition, ex);
                FeatureRuntime.Fail(Feature.Resistance, ex);
            }
        }
    }
}
