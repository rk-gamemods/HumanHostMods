using Animancer;
using System;
using HarmonyLib;
using UnityEngine;

namespace ExpandedHordes
{
    [HarmonyPatch(typeof(C_Controller_Base), "Play_Anim_BaseLayer")]
    internal static class HordeRunSpeed
    {
        private static readonly AccessTools.FieldRef<NPC_Horde_Mgr, Coroutine> Spawning =
            AccessTools.FieldRefAccess<NPC_Horde_Mgr, Coroutine>("_corHordeSpawn");

        private static void Prefix(C_Controller_Base __instance, AnimationClip clip,
            ClipTransition clipTran, ref float speed)
        {
            if (!FeatureRuntime.Enabled(Feature.Movement) || !(__instance is Zombie_Input zombie)) return;
            long started = PerformanceMonitor.Begin();
            try
            {
                NPC_Horde_Mgr horde = NPC_Horde_Mgr.ins;
                Creature_Mgr creatures = Creature_Mgr.ins;
                if (!horde || !creatures) return;

                // Input_WSAD passes this transition for NPC forward movement. Attack,
                // jump, idle and other clips retain their native animation speed.
                bool running = zombie._inRunning && zombie.Pressed_FastMove && zombie.Pressed_Move
                    && zombie.currCharState == C_Controller_Base.Controller_State.Grounded;
                bool runAnimation = clip == null && clipTran != null
                    && ReferenceEquals(clipTran, zombie.curr_Move_F);
                speed *= HordeRules.RunSpeedMultiplier(ModSettings.RunSpeedPercent.Value,
                    Spawning(horde) != null && !G_Save.isQuit, creatures._IsDayTime,
                    zombie._npcSpawnSource, running, runAnimation);
            }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Movement, ex); }
            finally { PerformanceMonitor.End(ProfileSection.RunSpeed, started); }
            // Only the call argument changes. The next native movement call restores
            // normal speed when spawning ends; no pooled or saved stat is modified.
        }
    }
}
