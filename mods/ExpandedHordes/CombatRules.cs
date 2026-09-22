using System;

namespace ExpandedHordes
{
    internal enum ZombieKind { Regular, Large, Boss }

    internal static class CombatRules
    {
        // Work on the requested loss before Unity clamps overkill to zero.
        // A lethal hit must remain lethal if its reduced damage still exceeds HP.
        internal static float ResistLoss(float current, float requested, int resistance)
        {
            if (!(current > 0f) || !(requested < current) || float.IsInfinity(current)
                || float.IsNaN(requested) || float.IsInfinity(requested)) return requested;
            double fraction = 1d - Math.Max(0, Math.Min(95, resistance)) / 100d;
            return (float)(current - ((double)current - requested) * fraction);
        }

        internal static int CorpseCapacity(int native, int configured) => Math.Max(native, configured);

        internal static ZombieKind Classify(bool boss, ZombieKind catalogKind) => boss ? ZombieKind.Boss : catalogKind;
    }
}
