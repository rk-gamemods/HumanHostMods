using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace AdminPanelFlyModeFix
{
    [BepInPlugin(Guid, "Admin Panel - Fly Mode Fix", "0.1.1")]
    [BepInDependency(AdminPanelCompatibility.AdminOwner, BepInDependency.DependencyFlags.SoftDependency)]
    public sealed class Plugin : BaseUnityPlugin
    {
        // Retain the original GUID across the display/assembly rename.
        public const string Guid = "rkgamemods.humanhost.zombierecovery";
        private readonly Dictionary<Zombie_Input, HoverObservation> observations = new Dictionary<Zombie_Input, HoverObservation>();
        private Harmony harmony;
        private AdminPanelCompatibility compatibility;
        private string output;
        private float nextScan, nextReport, recoverUntil;
        private string currentSave;
        private Vector3 previousOrigin;
        private int repaired;
        private bool runtimeReady;
        private bool failureLogged;
        private Report lastReport;

        [Serializable] private sealed class Report
        {
            public string utc, save, guard, game;
            public bool recovering, playerGroundLoaded;
            public int zombies, unsupported, stableCandidates, repaired;
            public Vector3 player, worldOrigin;
            public Row[] rows;
        }

        [Serializable] private sealed class Row
        {
            public int id;
            public string name, state, collider;
            public Vector3 position, worldPosition, velocity, momentum, lastValidPosition;
            public float gravity, clearance, groundY, rayLength;
            public bool groundFound, grounded, kinematic, fallen, registered, candidate, alive, eligible;
        }

        private void Awake()
        {
            output = Path.Combine(Paths.PluginPath, "Admin Panel - Fly Mode Fix", "diagnostics");
            Directory.CreateDirectory(output);
            harmony = new Harmony(Guid);
            compatibility = new AdminPanelCompatibility(harmony, Logger);
            try
            {
                compatibility.Install();
                compatibility.Install(); // Verify repeat installation is a no-op at the actual boundary.
            }
            catch (Exception ex) { Logger.LogError("Compatibility guard could not be installed: " + ex); }
            runtimeReady = Application.version == "0.8.316";
            Logger.LogInfo($"Admin Panel - Fly Mode Fix 0.1.1 loaded | game {Application.version} | recovery support={runtimeReady}. Automatic Admin Panel patch; Ctrl+Shift+F8: report; Ctrl+Shift+F9: attempt repair of stuck floating zombies for 120 seconds. Manual repair starts OFF.");
        }

        private void Update()
        {
            try { Tick(); }
            catch (Exception ex)
            {
                recoverUntil = 0;
                observations.Clear();
                if (!failureLogged) { failureLogged = true; Logger.LogError("Recovery stopped after an unexpected error: " + ex); }
            }
        }

        private void Tick()
        {
            bool shortcut = Input.GetKey(KeyCode.LeftControl) && Input.GetKey(KeyCode.LeftShift);
            if (shortcut && Input.GetKeyDown(KeyCode.F8)) { nextScan = nextReport = 0; }
            if (shortcut && Input.GetKeyDown(KeyCode.F9))
            {
                if (!runtimeReady) Logger.LogWarning("This game version has not been validated for recovery; no zombie state will be changed.");
                else if (!Player_Input.ins || G_Save.isQuit) Logger.LogWarning("Load a save before requesting recovery.");
                else if (recoverUntil > Time.time) Logger.LogInfo("Recovery already active; duplicate request ignored.");
                else
                {
                    recoverUntil = Time.time + 120f;
                    repaired = 0;
                    observations.Clear();
                    Logger.LogInfo("Recovery requested for the current save. Only stationary vertical motion above verified ground can qualify; falling, ragdoll and unsupported-terrain cases are excluded.");
                }
            }
            if (!Player_Input.ins || !Creature_Mgr.ins || !Terrain_Loader_Manager.ins || G_Save.isQuit)
            {
                observations.Clear(); recoverUntil = 0; currentSave = null; return;
            }
            var origin = Terrain_Loader_Manager.ins.neutralizedPlayerMove;
            if (currentSave != G_Save.ID)
            {
                currentSave = G_Save.ID; observations.Clear(); recoverUntil = 0; repaired = 0;
            }
            if (Creature_Mgr.ins._isWorldPullingBack || origin != previousOrigin)
            { observations.Clear(); previousOrigin = origin; return; }
            if (Time.timeScale <= 0f || !Player_Input.ins._feetGroundLoaded || Time.time < nextScan) return;
            nextScan = Time.time + 0.5f;
            Scan(origin);
        }

        private void Scan(Vector3 origin)
        {
            var zombies = UnityEngine.Object.FindObjectsOfType<Zombie_Input>();
            var current = new HashSet<Zombie_Input>(zombies);
            foreach (var old in observations.Keys.Where(z => !z || !current.Contains(z)).ToArray()) observations.Remove(old);
            var rows = new List<Row>();
            foreach (var zombie in zombies)
            {
                if (!zombie.rigidBody || !zombie._charMover || !zombie.capCol || !zombie.char_Status) continue;
                var position = zombie.rigidBody.position;
                var row = new Row {
                    id = zombie.GetInstanceID(), name = zombie.name, position = position, worldPosition = position - origin,
                    velocity = zombie.rigidBody.velocity, momentum = zombie.momentum, gravity = zombie.gravity,
                    lastValidPosition = zombie.lastValidPos, state = zombie.currCharState.ToString(),
                    grounded = zombie._charMover.isGrounded, kinematic = zombie.rigidBody.isKinematic, fallen = zombie._isFallGround,
                    alive = zombie.char_Status._CurrHP > 0f, registered = Creature_Mgr.ins._charFixedUpdates.Contains(zombie),
                    rayLength = zombie.heightLengthPlus5.y
                };
                RaycastHit ground = default;
                row.groundFound = zombie._mask_8_10.value != 0 && Physics.Raycast(position + Vector3.up * 0.5f, Vector3.down,
                    out ground, 4096f, zombie._mask_8_10, QueryTriggerInteraction.Ignore);
                if (row.groundFound)
                {
                    row.groundY = ground.point.y;
                    row.clearance = zombie.capCol.bounds.min.y - ground.point.y;
                    row.collider = ground.collider.name;
                }
                row.eligible = row.groundFound && row.alive && !row.kinematic && !row.fallen && row.registered
                    && zombie._NPC_Enabled && !zombie._inSfeScene && !zombie.transform.parent?.GetComponent<Rigidbody>()
                    && Vector3.Dot(zombie.transform.up, Vector3.up) > 0.98f;
                if (!observations.TryGetValue(zombie, out var observation)) observations.Add(zombie, observation = new HoverObservation());
                row.candidate = observation.Observe(Time.time, row.worldPosition.y, row.clearance, row.velocity.y, row.eligible);
                if (row.candidate && recoverUntil > Time.time && runtimeReady && TryPlace(zombie, row, ground))
                { repaired++; observation.Reset(); }
                rows.Add(row);
            }
            lastReport = new Report { utc = DateTime.UtcNow.ToString("O"), save = G_Save.ID, guard = compatibility.Status,
                game = Application.version, recovering = recoverUntil > Time.time, playerGroundLoaded = Player_Input.ins._feetGroundLoaded,
                player = Player_Input.ins.transform.position - origin, worldOrigin = origin, zombies = rows.Count,
                unsupported = rows.Count(r => r.groundFound && r.clearance >= HoverObservation.MinimumClearance),
                stableCandidates = rows.Count(r => r.candidate), repaired = repaired, rows = rows.ToArray() };
            if (Time.time >= nextReport)
            {
                nextReport = Time.time + 10f;
                File.WriteAllText(Path.Combine(output, "latest.json"), JsonUtility.ToJson(lastReport, true));
                Logger.LogInfo($"Scan save={currentSave} zombies={lastReport.zombies} unsupported={lastReport.unsupported} stable={lastReport.stableCandidates} repaired={repaired} recovery={lastReport.recovering}");
            }
        }

        private bool TryPlace(Zombie_Input zombie, Row before, RaycastHit ground)
        {
            if (ground.normal.y < 0.7f || !ground.collider || ground.collider.attachedRigidbody) return false;
            var capsule = zombie.capCol;
            if (capsule.direction != 1 || !capsule.enabled || !zombie.rigidBody.detectCollisions) return false;
            var scale = capsule.transform.lossyScale;
            float radius = capsule.radius * Mathf.Max(Mathf.Abs(scale.x), Mathf.Abs(scale.z));
            float height = Mathf.Max(capsule.height * Mathf.Abs(scale.y), radius * 2f);
            if (radius <= 0f || height <= 0f) return false;
            var target = before.position;
            target.y = ground.point.y - (capsule.bounds.min.y - before.position.y) + 0.1f;
            var center = capsule.transform.TransformPoint(capsule.center) + target - before.position;
            var segment = Vector3.up * (height * 0.5f - radius);
            if (Physics.CheckCapsule(center - segment, center + segment, radius, zombie._mask_8_10, QueryTriggerInteraction.Ignore)) return false;
            // Require support under the footprint, not just one ray through a gap or ledge.
            foreach (var direction in new[] { Vector3.right, Vector3.left, Vector3.forward, Vector3.back })
            {
                var start = ground.point + direction * radius * 0.7f + Vector3.up;
                if (!Physics.Raycast(start, Vector3.down, out var support, 2f, zombie._mask_8_10, QueryTriggerInteraction.Ignore)
                    || support.normal.y < 0.7f || Mathf.Abs(support.point.y - ground.point.y) > 0.6f) return false;
            }
            // A write-ahead record is required. If it fails, do not move this NPC.
            File.AppendAllText(Path.Combine(output, "recovery.jsonl"), JsonUtility.ToJson(new RecoveryEvent {
                phase = "before", utc = DateTime.UtcNow.ToString("O"), save = G_Save.ID, before = before, target = target }) + Environment.NewLine);
            zombie.rigidBody.position = target;
            zombie.transform.position = target;
            zombie.rigidBody.velocity = Vector3.zero;
            zombie.rigidBody.angularVelocity = Vector3.zero;
            zombie.momentum = Vector3.zero;
            zombie._charHighestY = target.y;
            zombie.Sync_AntiFall_Anchor();
            zombie._charMover.Reset_Rays();
            zombie.currCharState = C_Controller_Base.Controller_State.Falling;
            File.AppendAllText(Path.Combine(output, "recovery.jsonl"), JsonUtility.ToJson(new RecoveryEvent {
                phase = "placed", utc = DateTime.UtcNow.ToString("O"), save = G_Save.ID, before = before, target = target }) + Environment.NewLine);
            Logger.LogInfo($"Recovered {zombie.name} id={before.id}, clearance={before.clearance:F2}m, y={before.position.y:F2}->{target.y:F2}; health and inventory unchanged.");
            return true;
        }

        [Serializable] private sealed class RecoveryEvent
        { public string phase, utc, save; public Row before; public Vector3 target; }

        private void OnDestroy()
        {
            recoverUntil = 0;
            try { compatibility?.Restore(); }
            catch (Exception ex) { Logger.LogError("Could not restore original Admin Panel registrations during unload: " + ex); }
            harmony?.UnpatchSelf();
        }
    }
}
