using System;

namespace ZombieMovementFix
{
    internal static class RepairTransaction
    {
        internal static bool Apply(Func<MovementState> read, Action<MovementState> writeBefore,
            Action restore, Action<MovementState> writeAfter)
        {
            var before = read();
            if (before.Exclusion() != null) return false;
            writeBefore(before); // Must succeed before any movement/controller mutation.
            restore();
            var after = read();
            if (!after.enabled || !after.registered || after.health != before.health)
                throw new InvalidOperationException("Movement restoration did not register correctly or unexpectedly changed health.");
            writeAfter(after);
            return true;
        }
    }
}
