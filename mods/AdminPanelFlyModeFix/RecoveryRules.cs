using System;

namespace AdminPanelFlyModeFix
{
    internal static class GuardRules
    {
        internal const string KnownAdminSha256 = "a2b02ef182a1c1e88aa591ada1fc87adfb3e3b0a02ce6336328e0a246de0ac6d";
        internal delegate void StatePostfix(ref object state);

        internal static bool Recognizes(string version, string hash) =>
            version == "1.1.9" && string.Equals(hash, KnownAdminSha256, StringComparison.OrdinalIgnoreCase);

        internal static bool InputAllowed(bool isPlayer, Func<bool> original) => !isPlayer || original();

        internal static void ApplyState(bool isPlayer, ref object state, StatePostfix original)
        {
            if (isPlayer) original(ref state);
        }
    }

    // Uses elapsed game time, not wall time: pausing must not qualify a falling NPC.
    internal sealed class HoverObservation
    {
        internal const float MinimumClearance = 8f;
        internal const float RequiredSeconds = 6f;
        private float since = -1f;
        private float previousTime = -1f;
        private float initialHeight;

        internal bool Observe(float time, float worldHeight, float clearance, float verticalSpeed, bool eligible)
        {
            if (!eligible || !Finite(time) || !Finite(worldHeight) || !Finite(clearance) || !Finite(verticalSpeed)
                || clearance < MinimumClearance || Math.Abs(verticalSpeed) > 0.35f)
            {
                Reset();
                return false;
            }
            if (since < 0f || time < previousTime || time - previousTime > 1.5f || Math.Abs(worldHeight - initialHeight) > 0.35f)
            {
                since = time;
                initialHeight = worldHeight;
            }
            previousTime = time;
            return time - since >= RequiredSeconds;
        }

        internal void Reset() { since = previousTime = -1f; }
        internal static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
    }
}
