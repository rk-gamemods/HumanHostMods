using System;
using System.IO;
using System.Text.Json;
using ZombieMovementFix;

static class Program
{
    static int checks;
    static void Check(bool result, string message) { checks++; if (!result) throw new Exception(message); }
    static MovementState LivingDisabled() => new MovementState {
        health = 75, active = true, started = true, logicalNpc = true, owned = true,
        capsuleEnabled = true, collisions = true, upright = true, registrationClear = true
    };

    static void Main()
    {
        var state = LivingDisabled();
        Check(state.MissingMovement && state.Exclusion() == null, "Living disabled dynamic zombies need recovery independent of altitude or vertical velocity.");
        foreach (var change in new Action<MovementState>[] {
            s => s.health = 0, s => s.health = float.NaN, s => s.health = float.PositiveInfinity,
            s => s.active = false, s => s.started = false, s => s.logicalNpc = false,
            s => s.enabled = true, s => s.registered = true, s => s.owned = false,
            s => s.pendingDeath = true, s => s.kinematic = true, s => s.fallen = true,
            s => s.ragdoll = true, s => s.builtInGravity = true, s => s.capsuleEnabled = false,
            s => s.collisions = false, s => s.upright = false, s => s.registrationClear = false,
            s => s.safeScene = true, s => s.attached = true
        })
        {
            var excluded = LivingDisabled(); change(excluded);
            var observation = new DisabledObservation();
            Check(excluded.Exclusion() != null, "An unsafe state must have an explicit exclusion.");
            for (int i = 0; i <= 6; i++) Check(!observation.Observe(i * 0.5f, 1, excluded), "Time must never override an exclusion.");
        }
        var sample = new DisabledObservation();
        for (int i = 0; i < 4; i++) Check(!sample.Observe(i * 0.5f, 1, state), "Wait for disable callbacks and end-of-frame deregistration to settle.");
        Check(sample.Observe(2, 1, state), "Sustained missing movement must qualify after two game seconds.");
        state.enabled = state.registered = true;
        Check(!sample.Observe(2.5f, 1, state), "A successful repair or upstream correction must be a no-op on repeat.");
        state = LivingDisabled();
        Check(!sample.Observe(3, 2, state), "A reused object needs fresh observation.");
        Check(!sample.Observe(3.5f, 2, state), "A reused object must not inherit old qualification.");
        Check(!sample.Observe(4, 3, state), "A lifetime change resets qualification even at the same object ID.");
        for (int i = 0; i < 6; i++) Check(!sample.Observe(4, 3, state), "Paused game time cannot qualify.");
        Check(!sample.Observe(20, 3, state), "Streaming/measurement gaps reset qualification.");
        Check(!sample.Observe(1, 3, state), "Clock rollback resets qualification.");
        Check(!sample.Observe(float.NaN, 3, state), "Invalid timestamps reset observation.");
        sample.Observe(1, 3, state); sample.Observe(2, 3, state);
        state.pendingDeath = true;
        Check(!sample.Observe(3, 3, state), "A pending death must interrupt an otherwise qualified observation.");
        state.pendingDeath = false;
        Check(!sample.Observe(3.5f, 3, state), "A cleanup transition needs fresh qualification.");
        sample.Reset();
        Check(!sample.Observe(4, 3, state), "Explicit save/origin reset discards qualification.");

        CheckTransactions();
        CheckAudit();
        Console.WriteLine($"PASS: {checks} checks for disabled movement, lifecycle exclusions, repeated execution, timing and durable diagnostic records. Unity placement and OnEnable dispatch require user play testing.");
    }

    static void CheckTransactions()
    {
        var state = LivingDisabled();
        int beforeWrites = 0, moves = 0, afterWrites = 0;
        MovementState Read() => state;
        void Before(MovementState _) { beforeWrites++; }
        void Restore() { moves++; state = LivingDisabled(); state.enabled = state.registered = true; }
        void After(MovementState _) { afterWrites++; }
        Check(RepairTransaction.Apply(Read, Before, Restore, After), "A qualified repair must execute.");
        Check(beforeWrites == 1 && moves == 1 && afterWrites == 1, "One repair requires one write-ahead entry, restore and completion entry.");
        Check(!RepairTransaction.Apply(Read, Before, Restore, After) && moves == 1 && beforeWrites == 1, "Repeating the repair must not move or journal an already corrected zombie.");
        state = LivingDisabled();
        bool threw = false;
        try { RepairTransaction.Apply(Read, _ => throw new IOException("journal unavailable"), Restore, After); }
        catch (IOException) { threw = true; }
        Check(threw && moves == 1 && !state.enabled, "Journal failure must stop before mutation.");
        threw = false;
        try { RepairTransaction.Apply(Read, Before, () => { state = LivingDisabled(); state.enabled = true; }, After); }
        catch (InvalidOperationException) { threw = true; }
        Check(threw && afterWrites == 1, "Missing fixed-update registration must not be reported as success.");
        state = LivingDisabled(); threw = false;
        try { RepairTransaction.Apply(Read, Before, () => { Restore(); state.health--; }, After); }
        catch (InvalidOperationException) { threw = true; }
        Check(threw && afterWrites == 1, "Unexpected health changes must fail verification.");
        state = LivingDisabled(); threw = false;
        try { RepairTransaction.Apply(Read, Before, Restore, _ => throw new IOException("completion write failed")); }
        catch (IOException) { threw = true; }
        int previousMoves = moves;
        Check(threw && !RepairTransaction.Apply(Read, Before, Restore, After) && moves == previousMoves,
            "A completion-write failure followed by retry must not repeat a successful restore.");
        state = LivingDisabled(); state.pendingDeath = true;
        Check(!RepairTransaction.Apply(Read, Before, Restore, After) && moves == previousMoves, "Recheck corpse cleanup immediately before mutation.");
    }

    static void CheckAudit()
    {
        string folder = Path.Combine(Path.GetTempPath(), "ZombieMovementFix-" + Guid.NewGuid().ToString("N"));
        var audit = new Audit(folder);
        try
        {
            var record = new Record { phase = "before-repair", id = 123, generation = 2,
                name = "zombie \"example\"", state = LivingDisabled(), target = new Position(1, 2, 3) };
            audit.Append(record);
            using (var parsed = JsonDocument.Parse(File.ReadAllText(Path.Combine(folder, "events.jsonl"))))
            {
                Check(parsed.RootElement.GetProperty("state").GetProperty("health").GetSingle() == 75, "Journal must preserve pre-repair health.");
                Check(!parsed.RootElement.GetProperty("state").GetProperty("enabled").GetBoolean(), "Journal must preserve the actual disabled flag.");
                Check(parsed.RootElement.GetProperty("generation").GetInt32() == 2, "Journal must distinguish pooled lifetimes.");
                Check(parsed.RootElement.GetProperty("target").GetProperty("y").GetSingle() == 2, "Journal must preserve intended landing position.");
            }
            audit.WriteSummary(new Summary { unresolved = new[] { record }, missingMovement = 1 });
            audit.WriteSummary(new Summary { unresolved = Array.Empty<Record>(), repaired = 1 });
            using (var parsed = JsonDocument.Parse(File.ReadAllText(Path.Combine(folder, "latest.json"))))
                Check(parsed.RootElement.GetProperty("unresolved").GetArrayLength() == 0, "Repeated publication must replace stale failures.");
            // Make the journal path unwritable without changing ACLs or requiring elevation.
            File.Delete(Path.Combine(folder, "events.jsonl"));
            Directory.CreateDirectory(Path.Combine(folder, "events.jsonl"));
            bool failed = false;
            try { audit.Append(record); } catch (UnauthorizedAccessException) { failed = true; } catch (IOException) { failed = true; }
            Check(failed, "A failed write-ahead journal must throw so repair cannot proceed.");
            Directory.Delete(Path.Combine(folder, "events.jsonl"));
        }
        finally
        {
            foreach (var name in new[] { "events.jsonl", "latest.json", "latest.json.tmp" })
            { var path = Path.Combine(folder, name); if (File.Exists(path)) File.Delete(path); }
            Directory.Delete(folder);
        }
    }
}
