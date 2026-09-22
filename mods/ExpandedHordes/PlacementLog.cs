using HarmonyLib;
using UnityEngine;

namespace ExpandedHordes
{
    internal static class PlacementLog
    {
        private static int positions, rejected, contexts, missingContext;
        private static float lastReport;

        internal static void Reset()
        {
            Flush();
            positions = rejected = contexts = missingContext = 0;
            lastReport = float.NegativeInfinity;
        }

        internal static void Position(bool failure)
        {
            if (!ModSettings.DebugMode.Value || !FeatureRuntime.Enabled(Feature.Diagnostics)) return;
            positions++;
            if (failure) { rejected++; ReportIfDue(); }
        }

        internal static void Context(bool success)
        {
            if (!ModSettings.DebugMode.Value || !FeatureRuntime.Enabled(Feature.Diagnostics)) return;
            contexts++;
            if (!success) { missingContext++; ReportIfDue(); }
        }

        private static void ReportIfDue()
        {
            if (Time.realtimeSinceStartup - lastReport >= 30f) Flush();
        }

        internal static void Flush()
        {
            if (rejected == 0 && missingContext == 0) return;
            FeatureRuntime.DebugLog($"Horde placement since last report: {rejected}/{positions} rejected positions, {missingContext}/{contexts} missing terrain contexts. Native retries unchanged.");
            positions = rejected = contexts = missingContext = 0;
            lastReport = Time.realtimeSinceStartup;
        }
    }

    [HarmonyPatch(typeof(NPC_Horde_Mgr), "GetValidSpawnPosition")]
    internal static class PlacementResult
    {
        private static void Postfix(Vector3 __result, int maxAttempts)
        {
            bool rejected = __result.y == -10000f;
            if (!ModSettings.DebugMode.Value || !FeatureRuntime.Enabled(Feature.Diagnostics)) return;
            if (!rejected && maxAttempts == 100 && Player_Input.ins)
            {
                Vector3 delta = __result - Player_Input.ins.transform.position;
                rejected = delta.x * delta.x + delta.z * delta.z < 1600f;
            }
            PlacementLog.Position(rejected);
        }
    }

    [HarmonyPatch(typeof(NPC_Horde_Mgr), "Try_Get_Spawn_Context")]
    internal static class ContextResult
    {
        private static void Postfix(bool __result) => PlacementLog.Context(__result);
    }

    [HarmonyPatch(typeof(NPC_Horde_Mgr), "Save_Horde_Data_To_Disk")]
    internal static class PlacementSummary
    {
        private static void Prefix() => PlacementLog.Flush();
    }
}
