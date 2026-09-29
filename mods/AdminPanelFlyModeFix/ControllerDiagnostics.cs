using System.Collections.Generic;
using System.Linq;
using HarmonyLib;
using UnityEngine;

namespace AdminPanelFlyModeFix
{
    // Read-only probes: no controller fields, return values or arguments are changed.
    internal static class ControllerDiagnostics
    {
        private static readonly Dictionary<int, TraceSample> samples = new Dictionary<int, TraceSample>();

        internal static void Install(Harmony harmony)
        {
            harmony.Patch(AccessTools.DeclaredMethod(typeof(C_Controller_Base), "MyFixedUpdate"),
                postfix: new HarmonyMethod(typeof(ControllerDiagnostics), nameof(AfterFixed)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(C_Controller_Base), "Anti_Fallen_Into_EmptyAir_NPC"),
                prefix: new HarmonyMethod(typeof(ControllerDiagnostics), nameof(BeforeAntiFall)),
                postfix: new HarmonyMethod(typeof(ControllerDiagnostics), nameof(AfterAntiFall)));
        }

        internal static void Clear() => samples.Clear();
        internal static void Keep(HashSet<int> ids)
        {
            foreach (int id in samples.Keys.Where(id => !ids.Contains(id)).ToArray()) samples.Remove(id);
        }

        internal static TraceSample Get(int id)
        {
            if (!samples.TryGetValue(id, out var sample)) samples.Add(id, sample = new TraceSample());
            return sample;
        }

        private static void AfterFixed(C_Controller_Base __instance)
        {
            if (!(__instance is Zombie_Input)) return;
            var sample = Get(__instance.GetInstanceID());
            sample.fixedCalls++;
            sample.lastFixedTime = Time.time;
        }

        private static void BeforeAntiFall(C_Controller_Base __instance, out Vector3 __state)
        {
            __state = __instance is Zombie_Input && __instance.rigidBody ? __instance.rigidBody.position : Vector3.zero;
        }

        private static void AfterAntiFall(C_Controller_Base __instance, Vector3 __state)
        {
            if (!(__instance is Zombie_Input) || !__instance.rigidBody) return;
            var sample = Get(__instance.GetInstanceID());
            sample.antiFallCalls++;
            sample.lastAntiFallTime = Time.time;
            float y = __instance.rigidBody.position.y;
            if (Mathf.Abs(y - __state.y) <= 0.5f) return;
            sample.antiFallMoves++;
            sample.lastAntiFallMoveTime = Time.time;
            sample.lastAntiFallBeforeY = __state.y;
            sample.lastAntiFallAfterY = y;
        }
    }
}
