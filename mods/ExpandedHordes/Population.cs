using System;
using HarmonyLib;

namespace ExpandedHordes
{
    [HarmonyPatch(typeof(AI_Agen_Mgr), "MyStart")]
    internal static class AiSetup
    {
        private static void Prefix(AI_Agen_Mgr __instance)
        {
            if (!FeatureRuntime.Enabled(Feature.Population)) return;
            try { PopulationOverrides.SetAi(__instance, ModSettings.Allowance.Value); }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Population, ex); }
        }
    }

    [HarmonyPatch(typeof(AI_Agen_Mgr), "SetHorde_MaxAllowActiveZombies")]
    internal static class HordeAllowance
    {
        private static void Postfix()
        {
            if (!FeatureRuntime.Enabled(Feature.Population)) return;
            try { PopulationOverrides.SetLimit(NPC_Horde_Mgr.ins, Math.Min(ModSettings.Living.Value, ModSettings.Allowance.Value)); }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Population, ex); }
        }
    }

    [HarmonyPatch(typeof(NPC_Horde_Mgr), "Get_Plan_To_Spawn_Count")]
    internal static class SpawnBudget
    {
        private static bool Prefix(NPC_Horde_Mgr __instance, NPC_Horde_Mgr.Horde_Save_Data ____hordeSaveData,
            ref int ____HordeZombieAll, ref int ____ZombiesPioneerCount, ref int ____ZombiesPerWaveAdd, ref int __result)
        {
            if (!FeatureRuntime.Enabled(Feature.Population)) return true;
            int previousTotal = ____HordeZombieAll, previousPioneers = ____ZombiesPioneerCount,
                previousGrowth = ____ZombiesPerWaveAdd, previousLimit = __instance._MaxAllowActiveZombies;
            try
            {
                PopulationOverrides.Capture(__instance);
                float quantity = G_Save._config._Horde_Z_NumF;
                // Preserve a disabled/invalid native quantity without dividing by zero.
                if (!(quantity > 0f) || float.IsInfinity(quantity))
                {
                    __result = 0;
                    return false;
                }
                int target = Math.Min(ModSettings.Living.Value, ModSettings.Allowance.Value);
                ____HordeZombieAll = ModSettings.Total.Value;
                ____ZombiesPerWaveAdd = 0;
                // Native code multiplies this integer, then clamps to the allowance.
                // Round up here so fractional settings cannot undershoot the target.
                ____ZombiesPioneerCount = HordeRules.PioneerBase(target, quantity);
                __instance._MaxAllowActiveZombies = target;
                __result = HordeRules.Remaining(HordeRules.Budget(ModSettings.Total.Value, quantity), ____hordeSaveData.spawnedAlreadyCount);
                PopulationOverrides.Record(__instance);
                return false;
            }
            catch (Exception ex)
            {
                ____HordeZombieAll = previousTotal; ____ZombiesPioneerCount = previousPioneers;
                ____ZombiesPerWaveAdd = previousGrowth; __instance._MaxAllowActiveZombies = previousLimit;
                FeatureRuntime.Fail(Feature.Population, ex);
                return true;
            }
        }
    }

}
