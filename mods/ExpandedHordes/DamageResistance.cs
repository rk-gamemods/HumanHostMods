using System;
using HarmonyLib;

namespace ExpandedHordes
{
    [HarmonyPatch(typeof(Char_Status), "_CurrHP", MethodType.Setter)]
    internal static class DamageResistance
    {
        // The property is the common native damage boundary. Do not replace the setter,
        // touch maximum HP, or change the native XP/kill notification paths.
        [HarmonyPriority(Priority.Last)]
        private static void Prefix(Char_Status __instance, ref float value)
        {
            if (!FeatureRuntime.Enabled(Feature.Resistance) || G_Save.isQuit
                || !(value < __instance._CurrHP) || !(__instance._Controller is Zombie_Input zombie)
                || zombie._npcSpawnSource != 2 || !zombie.gameObject.activeInHierarchy) return;
            long started = PerformanceMonitor.Begin();
            try
            {
                var manager = NPC_Horde_Mgr.ins;
                // Registration follows initialization and is removed before the pool HP reset.
                // It persists after dawn and is restored by vanilla when loading survivors.
                if (!manager || !manager.spawned_Horde_NPCs.TryGetValue(zombie.gameObject, out var identity)) return;
                ZombieKind kind = CreatureCatalog.Classify(zombie.is_Boss, identity);
                int resistance = kind == ZombieKind.Boss ? ModSettings.BossResistance.Value
                    : kind == ZombieKind.Large ? ModSettings.LargeResistance.Value : ModSettings.RegularResistance.Value;
                value = CombatRules.ResistLoss(__instance._CurrHP, value, resistance);
            }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Resistance, ex); }
            finally { PerformanceMonitor.End(ProfileSection.Resistance, started); }
        }
    }
}
