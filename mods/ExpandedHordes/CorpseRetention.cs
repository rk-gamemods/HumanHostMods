using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection.Emit;
using HarmonyLib;

namespace ExpandedHordes
{
    [HarmonyPatch(typeof(GPUI_Dead_Body_Mgr), "Spawn_GPUI_Dead_Body")]
    internal static class CorpseRetention
    {
        private static IEnumerable<CodeInstruction> Transpiler(IEnumerable<CodeInstruction> instructions)
        {
            var code = instructions.ToList();
            var field = AccessTools.Field(typeof(G_Save.ConfigData), "_MaxCorpseCount");
            // Fail closed after a game update or incompatible rewrite. Do not guess at IL.
            if (field == null || code.Count(i => i.LoadsField(field)) != 1)
                throw new InvalidOperationException("Expected exactly one native corpse-limit read; corpse-limit patch was not applied.");
            var adjust = AccessTools.Method(typeof(CorpseRetention), nameof(EffectiveLimit));
            foreach (var instruction in code)
            {
                yield return instruction;
                if (instruction.LoadsField(field)) yield return new CodeInstruction(OpCodes.Call, adjust);
            }
        }

        internal static int EffectiveLimit(int native) => FeatureRuntime.Enabled(Feature.Corpses)
            ? CombatRules.CorpseCapacity(native, ModSettings.CorpseLimit.Value) : native;
    }
}
