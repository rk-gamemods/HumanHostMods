using System;
using System.Runtime.Serialization;

namespace ZombieMovementFix
{
    [DataContract]
    internal sealed class MovementState
    {
        [DataMember] public float health;
        [DataMember] public bool active, started, logicalNpc, enabled, registered, owned, pendingDeath;
        [DataMember] public bool kinematic, fallen, ragdoll, builtInGravity, capsuleEnabled, collisions, upright;
        [DataMember] public bool registrationClear, safeScene, attached;

        internal bool MissingMovement => health > 0 && !enabled && !registered && !kinematic && !fallen && !builtInGravity;

        internal string Exclusion()
        {
            if (!Finite(health) || health <= 0) return "dead or invalid health";
            if (enabled || registered) return "movement already enabled or registered";
            if (!active || !started || !logicalNpc) return "inactive or initialization incomplete";
            if (!owned) return "not in the game's living spawn registry";
            if (pendingDeath) return "awaiting corpse cleanup";
            if (kinematic || fallen || ragdoll) return "ragdoll or inactive physics";
            if (builtInGravity) return "different gravity setup";
            if (!capsuleEnabled || !collisions || !upright) return "unsuitable collision body";
            if (!registrationClear) return "existing collider registration";
            if (safeScene || attached) return "safe scene or attached body";
            return null;
        }

        internal static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);
    }

    // Observe the broken lifecycle state, not a guessed altitude or direction of travel.
    internal sealed class DisabledObservation
    {
        private float since = -1, previous = -1;
        private int generation = -1;

        internal bool Observe(float time, int lifetime, MovementState state)
        {
            if (!MovementState.Finite(time) || state.Exclusion() != null) { Reset(); return false; }
            if (since < 0 || generation != lifetime || time < previous || time - previous > 1.5f)
            { since = time; generation = lifetime; }
            previous = time;
            return time - since >= 2f;
        }

        internal void Reset() { since = previous = -1; generation = -1; }
    }
}
