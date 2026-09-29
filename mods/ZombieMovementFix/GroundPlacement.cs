using UnityEngine;

namespace ZombieMovementFix
{
    internal static class GroundPlacement
    {
        internal static bool TryTarget(Zombie_Input zombie, out Vector3 target, out string reason)
        {
            target = zombie.rigidBody.position;
            reason = "ground or safe standing space unavailable";
            var capsule = zombie.capCol;
            if (!Finite(target) || !Finite(zombie.rigidBody.velocity) || capsule.direction != 1 || zombie._mask_8_10.value == 0) return false;
            if (!Physics.Raycast(target + Vector3.up * 0.5f, Vector3.down, out var ground, 4096f,
                zombie._mask_8_10, QueryTriggerInteraction.Ignore)) return false;
            if (!ground.collider || ground.collider.attachedRigidbody || ground.normal.y < 0.7f) return false;
            float clearance = capsule.bounds.min.y - ground.point.y;
            // Never dig an NPC out of terrain or move it horizontally. Existing near-ground
            // placement needs only controller restoration; raised bodies need a safe landing.
            if (clearance < -0.2f) return false;
            if (clearance <= 0.5f) { reason = "restore movement at current ground position"; return true; }
            var scale = capsule.transform.lossyScale;
            float radius = capsule.radius * Mathf.Max(Mathf.Abs(scale.x), Mathf.Abs(scale.z));
            float height = Mathf.Max(capsule.height * Mathf.Abs(scale.y), radius * 2f);
            if (!MovementState.Finite(radius) || !MovementState.Finite(height) || radius <= 0 || height <= 0) return false;
            target.y = ground.point.y - (capsule.bounds.min.y - target.y) + 0.1f;
            var center = capsule.transform.TransformPoint(capsule.center) + target - zombie.rigidBody.position;
            var segment = Vector3.up * (height * 0.5f - radius);
            // Test all collision layers this capsule actually collides with, including other NPCs.
            int mask = 0;
            for (int layer = 0; layer < 32; layer++)
                if (!Physics.GetIgnoreLayerCollision(capsule.gameObject.layer, layer)) mask |= 1 << layer;
            foreach (var other in Physics.OverlapCapsule(center - segment, center + segment, radius, mask, QueryTriggerInteraction.Ignore))
                if (other.attachedRigidbody != zombie.rigidBody && !other.transform.IsChildOf(zombie.transform)) return false;
            foreach (var direction in new[] { Vector3.right, Vector3.left, Vector3.forward, Vector3.back })
            {
                var start = ground.point + direction * radius * 0.7f + Vector3.up;
                if (!Physics.Raycast(start, Vector3.down, out var support, 2f, zombie._mask_8_10, QueryTriggerInteraction.Ignore)
                    || support.collider.attachedRigidbody || support.normal.y < 0.7f || Mathf.Abs(support.point.y - ground.point.y) > 0.6f) return false;
            }
            reason = "place on verified ground and restore movement";
            return Finite(target);
        }

        internal static bool Finite(Vector3 value) => MovementState.Finite(value.x) && MovementState.Finite(value.y) && MovementState.Finite(value.z);
    }
}
