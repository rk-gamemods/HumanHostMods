using System;
using System.Collections;
using HarmonyLib;
using UnityEngine;

namespace ExpandedHordes
{
    internal static class HordeAttraction
    {
        internal static IEnumerator Safely(IEnumerator work)
        {
            try
            {
                while (FeatureRuntime.Enabled(Feature.Attraction))
                {
                    object next;
                    try { if (!work.MoveNext()) yield break; next = work.Current; }
                    catch (Exception ex) { FeatureRuntime.Fail(Feature.Attraction, ex); yield break; }
                    yield return next;
                }
            }
            finally { (work as IDisposable)?.Dispose(); }
        }
        private static readonly AccessTools.FieldRef<AI_Agen_Mgr, Coroutine> Sorting =
            AccessTools.FieldRefAccess<AI_Agen_Mgr, Coroutine>("_InWaitSorting");

        internal static IEnumerator AttractOnce(NPC_Horde_Mgr owner)
        {
            AI_Agen_Mgr ai = AI_Agen_Mgr.ins;
            Player_Input player = Player_Input.ins;
            if (!ai || !player) yield break;
            // Broadcast_Sound_Played drops notifications while sorting. Wait for it,
            // without adding a recurring attraction loop or retaining work across scenes.
            float deadline = Time.realtimeSinceStartup + 5f;
            for (int i = 0; i < 2; i++)
            {
                while (ai && Sorting(ai) != null && Time.realtimeSinceStartup < deadline)
                    yield return null;
                if (!owner || !ai || !player || G_Save.isQuit || Creature_Mgr.ins._IsDayTime)
                    yield break;
                if (Sorting(ai) != null)
                {
                    Plugin.Log.LogWarning("One-time attraction skipped: native sound selection remained busy.");
                    yield break;
                }
                Vector3 position = player._ragDollMgr._headBodyScript.transform.position;
                if (i == 1) position += Vector3.up * ModSettings.AttractionHeight.Value;
                ai.Broadcast_Sound_Played(new Creature_Mgr.OnSoundPlayed_Param
                {
                    charController = player,
                    soundSource = player._ragDollMgr._ChestBoxCollider,
                    sourceRadius = player.capCol.radius,
                    soundSourcePos = position,
                    hearDis = ModSettings.AttractionRadius.Value
                });
            }
            FeatureRuntime.DebugLog("Horde start: sent the two one-time silent attraction notifications.");
        }
    }

    [HarmonyPatch(typeof(NPC_Horde_Mgr), "StartHordeEvent")]
    internal static class HordeStart
    {
        private static void Prefix(NPC_Horde_Mgr.Horde_Save_Data ____hordeSaveData, out int __state) =>
            __state = ____hordeSaveData?.spawnedWaveCount ?? -1;

        private static void Postfix(NPC_Horde_Mgr __instance, bool isLoad,
            NPC_Horde_Mgr.Horde_Save_Data ____hordeSaveData, int __state)
        {
            if (isLoad || ____hordeSaveData == null || ____hordeSaveData.spawnedWaveCount == __state || !FeatureRuntime.Enabled(Feature.Attraction)) return;
            try
            {
                PlacementLog.Flush();
                int budget = HordeRules.Budget(ModSettings.Total.Value, G_Save._config._Horde_Z_NumF);
                FeatureRuntime.DebugLog($"Horde {____hordeSaveData.spawnedWaveCount} started: budget {budget} (base {ModSettings.Total.Value}, Horde Quantity {G_Save._config._Horde_Z_NumF * 100f}%), living target {Math.Min(ModSettings.Living.Value, ModSettings.Allowance.Value)}.");
                __instance.StartCoroutine(HordeAttraction.Safely(HordeAttraction.AttractOnce(__instance)));
            }
            catch (Exception ex) { FeatureRuntime.Fail(Feature.Attraction, ex); }
        }
    }
}
