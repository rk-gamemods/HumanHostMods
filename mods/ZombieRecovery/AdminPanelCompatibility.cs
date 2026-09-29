using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using BepInEx.Bootstrap;
using BepInEx.Logging;
using HarmonyLib;

namespace ZombieRecovery
{
    internal sealed class AdminPanelCompatibility
    {
        internal const string AdminOwner = "humanhost.admin.panel";
        private readonly Harmony harmony;
        private readonly ManualLogSource log;
        private Entry[] entries;
        private bool installed;
        private static GuardRules.StatePostfix originalState;
        private static Func<bool> originalInput;
        internal string Status { get; private set; } = "not checked";

        private sealed class Entry
        {
            internal MethodInfo Target;
            internal Patch Previous;
            internal MethodInfo Wrapper;
            internal bool IsPrefix;
        }

        internal AdminPanelCompatibility(Harmony harmony, ManualLogSource log)
        { this.harmony = harmony; this.log = log; }

        internal void Install()
        {
            if (installed) return;
            if (!Chainloader.PluginInfos.TryGetValue(AdminOwner, out var info))
            { Status = "Admin Panel absent; guard not needed"; log.LogInfo(Status); return; }
            string hash;
            using (var file = File.OpenRead(info.Instance.GetType().Assembly.Location))
            using (var sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
            if (!GuardRules.Recognizes(info.Metadata.Version.ToString(), hash))
            {
                Status = "Admin Panel implementation changed; compatibility guard left inactive";
                log.LogWarning($"{Status} (version={info.Metadata.Version}, sha256={hash}). No upstream patches changed.");
                return;
            }

            var type = info.Instance.GetType();
            var statePatch = AccessTools.DeclaredMethod(type, "DetermineControllerState_Postfix");
            var inputPatch = AccessTools.DeclaredMethod(type, "Input_WSAD_Prefix");
            if (statePatch == null || inputPatch == null || !statePatch.IsStatic || !inputPatch.IsStatic
                || statePatch.ReturnType != typeof(void) || statePatch.GetParameters().Length != 1
                || statePatch.GetParameters()[0].ParameterType != typeof(object).MakeByRefType()
                || inputPatch.ReturnType != typeof(bool) || inputPatch.GetParameters().Length != 0)
                throw new InvalidOperationException("Known Admin Panel patch signatures were not found.");

            entries = new[] {
                Prepare("DetermineControllerState", statePatch, nameof(StatePostfix), false),
                Prepare("Input_WSAD", inputPatch, nameof(InputPrefix), true)
            };
            // Validate both registrations and delegates before changing either target.
            originalState = (GuardRules.StatePostfix)Delegate.CreateDelegate(typeof(GuardRules.StatePostfix), statePatch);
            originalInput = (Func<bool>)Delegate.CreateDelegate(typeof(Func<bool>), inputPatch);
            try
            {
                foreach (var entry in entries)
                {
                    var replacement = Metadata(entry.Wrapper, entry.Previous);
                    harmony.Patch(entry.Target, entry.IsPrefix ? replacement : null, entry.IsPrefix ? null : replacement);
                    harmony.Unpatch(entry.Target, entry.Previous.PatchMethod);
                }
                Verify();
                installed = true;
                Status = "Admin Panel 1.1.9 guarded: 2 player-only replacements verified";
                log.LogInfo(Status);
            }
            catch
            {
                Restore();
                throw;
            }
        }

        private static Entry Prepare(string member, MethodInfo oldPatch, string wrapper, bool prefix)
        {
            var target = AccessTools.DeclaredMethod(typeof(C_Controller_Base), member)
                ?? throw new MissingMethodException(typeof(C_Controller_Base).FullName, member);
            var patches = Harmony.GetPatchInfo(target);
            var matches = (prefix ? patches?.Prefixes : patches?.Postfixes)?
                .Where(p => p.owner == AdminOwner && p.PatchMethod == oldPatch).ToArray();
            if (matches == null || matches.Length != 1)
                throw new InvalidOperationException($"Expected exactly one original Admin Panel patch on {member}; leaving unknown layout alone.");
            return new Entry { Target = target, Previous = matches[0], Wrapper = AccessTools.DeclaredMethod(typeof(AdminPanelCompatibility), wrapper), IsPrefix = prefix };
        }

        private static HarmonyMethod Metadata(MethodInfo method, Patch previous) => new HarmonyMethod(method)
        { priority = previous.priority, before = previous.before, after = previous.after };

        private void Verify()
        {
            foreach (var entry in entries)
            {
                var info = Harmony.GetPatchInfo(entry.Target);
                var current = entry.IsPrefix ? info.Prefixes : info.Postfixes;
                if (current.Count(p => p.owner == Plugin.Guid && p.PatchMethod == entry.Wrapper) != 1
                    || current.Any(p => p.PatchMethod == entry.Previous.PatchMethod))
                    throw new InvalidOperationException("Compatibility replacement did not reach its expected patch layout.");
            }
        }

        internal void Restore()
        {
            if (entries == null) return;
            foreach (var entry in entries)
            {
                harmony.Unpatch(entry.Target, entry.Wrapper);
                var info = Harmony.GetPatchInfo(entry.Target);
                var current = entry.IsPrefix ? info?.Prefixes : info?.Postfixes;
                if (current == null || !current.Any(p => p.PatchMethod == entry.Previous.PatchMethod))
                {
                    var previous = Metadata(entry.Previous.PatchMethod, entry.Previous);
                    new Harmony(entry.Previous.owner).Patch(entry.Target, entry.IsPrefix ? previous : null, entry.IsPrefix ? null : previous);
                }
            }
            entries = null;
            installed = false;
        }

        private static void StatePostfix(C_Controller_Base __instance, ref C_Controller_Base.Controller_State __result)
        {
            object state = __result;
            GuardRules.ApplyState(__instance && __instance._isPlayer, ref state, originalState);
            __result = (C_Controller_Base.Controller_State)state;
        }

        private static bool InputPrefix(C_Controller_Base __instance) =>
            GuardRules.InputAllowed(__instance && __instance._isPlayer, originalInput);
    }
}
