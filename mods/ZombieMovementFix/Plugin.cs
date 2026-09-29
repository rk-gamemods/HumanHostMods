using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace ZombieMovementFix
{
    [BepInPlugin(Guid, "Human Host - Zombie Movement Fix", "0.1.0")]
    public sealed class Plugin : BaseUnityPlugin
    {
        public const string Guid = "rkgamemods.humanhost.zombiemovementfix";
        private readonly Dictionary<Zombie_Input, DisabledObservation> observations = new Dictionary<Zombie_Input, DisabledObservation>();
        private readonly Dictionary<Zombie_Input, int> generations = new Dictionary<Zombie_Input, int>();
        private readonly HashSet<Zombie_Input> failed = new HashSet<Zombie_Input>();
        private static Plugin instance;
        private FieldInfo allowEnable, livingHorde;
        private Harmony harmony;
        private Audit audit;
        private bool ready;
        private string save;
        private Vector3 origin;
        private float nextScan, nextReport;
        private int repaired;

        private void Awake()
        {
            instance = this;
            audit = new Audit(Path.Combine(Path.GetDirectoryName(Info.Location), "diagnostics"));
            // Same version strings can ship different code. Stop on either assembly change.
            if (Application.version != "0.8.316"
                || !Matches(typeof(C_Controller_Base).Assembly, "62f4cc7b8d070dd6f422624b9f4f565b632f1f3a9fcc6d388f0bbb85777fea93")
                || !Matches(typeof(NPC_Horde_Mgr).Assembly, "9d7aa125d6037ad943c7baf2724edf2e9ffe713ec939dc2a6fa3881d1ff15fd0"))
            { Logger.LogWarning("Game code changed: Zombie Movement Fix is inactive pending review."); return; }
            allowEnable = AccessTools.Field(typeof(C_Controller_Base), "_allowEnable");
            livingHorde = AccessTools.Field(typeof(NPC_Horde_Mgr), "_aliveHordeNPCs");
            if (allowEnable?.FieldType != typeof(bool) || livingHorde == null) throw new InvalidOperationException("Game lifecycle fields unavailable.");
            harmony = new Harmony(Guid);
            harmony.Patch(AccessTools.DeclaredMethod(typeof(Zombie_Input), "OnDisable"), postfix: new HarmonyMethod(typeof(Plugin), nameof(AfterDisable)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(Zombie_Input), "On_Char_Died"), postfix: new HarmonyMethod(typeof(Plugin), nameof(AfterDeath)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPC_Horde_Mgr), "Broadcast_Npc_Focus_Player_Event"), postfix: new HarmonyMethod(typeof(Plugin), nameof(AfterHordeSpawn)));
            harmony.Patch(AccessTools.DeclaredMethod(typeof(NPC_Horde_Mgr), "Put_NPC_Back_To_Pool"), postfix: new HarmonyMethod(typeof(Plugin), nameof(AfterPool)));
            ready = true;
            Logger.LogInfo("Human Host - Zombie Movement Fix 0.1.0 loaded. Automatic repair of disabled movement on living zombies; no hotkey required. Game code verified.");
        }

        private static bool Matches(Assembly assembly, string expected)
        {
            using (var hash = SHA256.Create())
            using (var file = File.OpenRead(assembly.Location))
                return BitConverter.ToString(hash.ComputeHash(file)).Replace("-", "").Equals(expected, StringComparison.OrdinalIgnoreCase);
        }

        private void Update()
        {
            if (!ready) return;
            try { Tick(); }
            catch (Exception ex) { ready = false; Logger.LogError("Zombie movement repair stopped after an error: " + ex); }
        }

        private void Tick()
        {
            if (G_Save.isQuit || !Player_Input.ins || !Creature_Mgr.ins || !NPC_Spawner_Mgr.ins || !NPC_Horde_Mgr.ins || !Terrain_Loader_Manager.ins || !Global_Update.ins)
            { Clear(); save = null; return; }
            var newOrigin = Terrain_Loader_Manager.ins.neutralizedPlayerMove;
            if (save != G_Save.ID) { Clear(); save = G_Save.ID; repaired = 0; }
            if (Creature_Mgr.ins._isWorldPullingBack || newOrigin != origin) { Clear(); origin = newOrigin; return; }
            // PauseMod uses a tiny positive time scale; do not treat it as active gameplay.
            if (Time.timeScale < 0.001f || !Player_Input.ins._feetGroundLoaded) { observations.Clear(); return; }
            if (Time.time < nextScan) return;
            nextScan = Time.time + 0.5f;
            var zombies = UnityEngine.Object.FindObjectsOfType<Zombie_Input>();
            var active = new HashSet<Zombie_Input>(zombies);
            foreach (var old in observations.Keys.Where(z => !z || !active.Contains(z)).ToArray()) observations.Remove(old);
            foreach (var old in generations.Keys.Where(z => !z || !active.Contains(z)).ToArray()) generations.Remove(old);
            failed.RemoveWhere(z => !z || !active.Contains(z));
            var unresolved = new List<Record>();
            int missing = 0;
            foreach (var zombie in zombies)
            {
                if (!zombie.char_Status || !zombie.rigidBody || !zombie.capCol || !zombie._charMover) continue;
                var state = Read(zombie);
                if (!state.MissingMovement) { observations.Remove(zombie); continue; }
                missing++;
                var record = MakeRecord("observed", zombie, state);
                string exclusion = state.Exclusion();
                if (exclusion != null || failed.Contains(zombie))
                {
                    observations.Remove(zombie);
                    record.detail = exclusion ?? "previous repair failed; no repeated mutation";
                }
                else
                {
                    if (!observations.TryGetValue(zombie, out var observation)) observations.Add(zombie, observation = new DisabledObservation());
                    if (!observation.Observe(Time.time, record.generation, state)) record.detail = "waiting for two seconds of disabled movement";
                    else if (!GroundPlacement.TryTarget(zombie, out var target, out var reason)) record.detail = reason;
                    else
                    {
                        // Recheck immediately at the mutation boundary, after all placement work.
                        if (Read(zombie).Exclusion() == null)
                        {
                            Repair(zombie, record, target, reason);
                            observations.Remove(zombie);
                            continue;
                        }
                        record.detail = "lifecycle changed before repair";
                    }
                }
                unresolved.Add(record);
            }
            if (Time.time < nextReport) return;
            nextReport = Time.time + 10;
            audit.WriteSummary(new Summary { utc = DateTime.UtcNow.ToString("O"), save = save,
                checkedZombies = zombies.Length, missingMovement = missing, repaired = repaired, unresolved = unresolved.ToArray() });
            Logger.LogInfo($"Movement scan: zombies={zombies.Length}, missing movement before repair={missing}, unresolved={unresolved.Count}, repaired this session={repaired}.");
        }

        private MovementState Read(Zombie_Input zombie)
        {
            var manager = Creature_Mgr.ins;
            bool owned = false;
            if (zombie._npcSpawnSource == 2 && NPC_Horde_Mgr.ins)
                owned = NPC_Horde_Mgr.ins.spawned_Horde_NPCs.ContainsKey(zombie.gameObject)
                    && ((IDictionary)livingHorde.GetValue(NPC_Horde_Mgr.ins)).Contains(zombie.gameObject);
            else if (zombie._npcSpawnSource == 1 && NPC_Spawner_Mgr.ins)
                owned = NPC_Spawner_Mgr.ins.spawned_NPCs.ContainsKey(zombie.gameObject);
            return new MovementState {
                health = zombie.char_Status ? zombie.char_Status._CurrHP : 0,
                active = zombie.gameObject.activeInHierarchy, started = (bool)allowEnable.GetValue(zombie),
                logicalNpc = zombie._NPC_Enabled, enabled = zombie.enabled,
                registered = manager && manager._charFixedUpdates.Contains(zombie), owned = owned,
                pendingDeath = !NPC_Spawner_Mgr.ins || NPC_Spawner_Mgr.ins._waitBackPoolDead_NPCs.ContainsKey(zombie.gameObject),
                kinematic = !zombie.rigidBody || zombie.rigidBody.isKinematic, fallen = zombie._isFallGround,
                ragdoll = zombie._ragDollMgr || !zombie._CharGPUIRender || zombie._CharGPUIRender._switchToAnimancerAlready,
                builtInGravity = zombie.rigidBody && zombie.rigidBody.useGravity,
                capsuleEnabled = zombie.capCol && zombie.capCol.enabled, collisions = zombie.rigidBody && zombie.rigidBody.detectCollisions,
                upright = Vector3.Dot(zombie.transform.up, Vector3.up) > 0.98f,
                registrationClear = manager && zombie.capCol && !manager.capCol_To_Controller.ContainsKey(zombie.capCol)
                    && (!zombie._capTrigger || !manager.capCol_To_Controller.ContainsKey(zombie._capTrigger)),
                safeScene = zombie._inSfeScene, attached = zombie.transform.parent && zombie.transform.parent.GetComponent<Rigidbody>()
            };
        }

        private void Repair(Zombie_Input zombie, Record before, Vector3 target, string reason)
        {
            RepairTransaction.Apply(() => Read(zombie), state => {
                before.state = state;
                before.phase = "before-repair"; before.target = P(target); before.detail = reason;
                audit.Append(before);
            }, () => {
                // Record failure before touching state; a partial attempt must not loop indefinitely.
                failed.Add(zombie);
                zombie.rigidBody.velocity = Vector3.zero;
                zombie.rigidBody.angularVelocity = Vector3.zero;
                zombie.momentum = Vector3.zero;
                zombie.rigidBody.position = target;
                zombie.transform.position = target;
                zombie._charHighestY = target.y;
                zombie.Sync_AntiFall_Anchor();
                zombie._charMover.Reset_Rays();
                zombie.currCharState = C_Controller_Base.Controller_State.Falling;
                // Unity dispatches Zombie_Input.OnEnable, restoring AI, gravity, collider mapping,
                // day/night listeners and the anti-fall callback through the game's normal path.
                zombie.enabled = true;
            }, after => {
                var completed = MakeRecord("repaired", zombie, after);
                completed.target = P(target); completed.detail = reason;
                audit.Append(completed);
                repaired++;
                Logger.LogInfo($"Restored {zombie.name} id={before.id}: y={before.position.y:F2}->{target.y:F2}; movement registered; HP={after.health:F1} unchanged.");
            });
        }

        private Record MakeRecord(string phase, Zombie_Input zombie, MovementState state) => new Record {
            phase = phase, utc = DateTime.UtcNow.ToString("O"), save = G_Save.ID, gameTime = Time.time,
            name = zombie.name, id = zombie.GetInstanceID(), generation = generations.TryGetValue(zombie, out int generation) ? generation : 0,
            spawnSource = zombie._npcSpawnSource, state = state, position = P(zombie.transform.position),
            worldOrigin = Terrain_Loader_Manager.ins ? P(Terrain_Loader_Manager.ins.neutralizedPlayerMove) : default,
            velocity = zombie.rigidBody ? P(zombie.rigidBody.velocity) : default
        };

        private static Position P(Vector3 point) => new Position(point.x, point.y, point.z);
        private void Clear() { observations.Clear(); generations.Clear(); failed.Clear(); }

        // Read-only lifecycle records distinguish pool reuse from movement during one lifetime.
        private static void AfterDisable(Zombie_Input __instance) => ObserveEvent("disabled", __instance, false);
        private static void AfterDeath(Zombie_Input __instance) => ObserveEvent("death-completed", __instance, false);
        private static void AfterPool(GameObject __0) { if (__0) ObserveEvent("returned-to-pool", __0.GetComponent<Zombie_Input>(), true); }
        private static void AfterHordeSpawn(GameObject __0, bool __2)
        { if (__0 && __2) ObserveEvent("spawn-ready", __0.GetComponent<Zombie_Input>(), true); }

        private static void ObserveEvent(string phase, Zombie_Input zombie, bool nextLifetime)
        {
            if (!instance || !instance.ready || !zombie || G_Save.isQuit) return;
            try
            {
                instance.observations.Remove(zombie);
                if (nextLifetime)
                {
                    instance.generations.TryGetValue(zombie, out int prior);
                    instance.generations[zombie] = prior + 1;
                    instance.failed.Remove(zombie);
                }
                var state = instance.Read(zombie);
                var record = instance.MakeRecord(phase, zombie, state);
                if (phase == "disabled" && state.active && state.health > 0)
                {
                    string stack = new System.Diagnostics.StackTrace(2, false).ToString();
                    record.detail = stack.Length > 4000 ? stack.Substring(0, 4000) : stack;
                }
                instance.audit.Append(record);
            }
            catch (Exception ex)
            {
                // A diagnostic hook must never propagate an exception into game lifecycle code.
                instance.ready = false;
                instance.Logger.LogError("Movement diagnostics failed; repair disabled: " + ex.Message);
            }
        }

        private void OnDestroy() { ready = false; harmony?.UnpatchSelf(); if (instance == this) instance = null; }
    }
}
