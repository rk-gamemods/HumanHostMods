using System;

namespace ExpandedHordes
{
    // Pure policy shared with the small executable checks; no game state or saved data.
    internal static class HordeRules
    {
        internal static int Budget(int baseTotal, float quantityMultiplier)
        {
            if (!(quantityMultiplier > 0f) || float.IsInfinity(quantityMultiplier)) return 0;
            return (int)Math.Min(int.MaxValue, Math.Max(0d,
                Math.Round(baseTotal * (double)quantityMultiplier, MidpointRounding.ToEven)));
        }

        internal static float RunSpeedMultiplier(int percentage, bool spawning, bool daytime,
            int spawnSource, bool running, bool runAnimation) =>
            spawning && !daytime && spawnSource == 2 && running && runAnimation
                ? percentage / 100f : 1f;

        internal static int Remaining(int total, int spawned) =>
            (int)Math.Max(0L, (long)total - Math.Max(0, spawned));

        internal static int PioneerBase(int living, float quantityMultiplier) =>
            (int)Math.Min(int.MaxValue, Math.Ceiling(living / (double)quantityMultiplier));

        internal static int Region(float x, float z, float gridWidth, float biomeWidth)
        {
            double gx = Math.Round(x / gridWidth, MidpointRounding.ToEven) * gridWidth;
            double gz = Math.Round(z / gridWidth, MidpointRounding.ToEven) * gridWidth;
            return Math.Max(1, 1 + (int)Math.Floor((Math.Sqrt(gx * gx + gz * gz) - 12) / biomeWidth));
        }

        // Disjoint chances: a disabled category's probability goes back to vanilla.
        internal static int Category(int roll, int region, int largeBegin, int bossBegin,
            int largePercent, int bossPercent)
        {
            int boss = region >= bossBegin ? bossPercent : 0;
            int large = region >= largeBegin ? largePercent : 0;
            return roll < boss ? 2 : roll < boss + large ? 1 : 0;
        }
    }
}
