using System;
using System.IO;
using System.Runtime.Serialization;
using System.Text.Json;
using AdminPanelFlyModeFix;

static class Program
{
    static int assertions;
    static void Check(bool result, string message)
    {
        assertions++;
        if (!result) throw new Exception(message);
    }

    static bool ObserveFor(HoverObservation sample, float start, float height = 100, float clearance = 90,
        float velocity = 0, bool eligible = true)
    {
        bool result = false;
        for (int i = 0; i <= 12; i++) result = sample.Observe(start + i * 0.5f, height, clearance, velocity, eligible);
        return result;
    }

    static int Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--check-report")
        {
            try
            {
                var report = DiagnosticJson.ReadReport(File.ReadAllText(args[1]));
                Console.WriteLine($"PASS: {report.rows.Length} complete zombie rows.");
                return 0;
            }
            catch (SerializationException ex) { Console.WriteLine("FAIL: " + ex.Message); return 1; }
        }
        Check(GuardRules.Recognizes("1.1.9", GuardRules.KnownAdminSha256), "Known broken build must qualify.");
        Check(!GuardRules.Recognizes("1.1.10", GuardRules.KnownAdminSha256), "Updated version must remain untouched.");
        Check(!GuardRules.Recognizes("1.1.9", new string('0', 64)), "Changed code with unchanged version must remain untouched.");
        Check(!GuardRules.Recognizes(null, null), "Missing identity must remain untouched.");

        bool fly = true;
        int calls = 0;
        bool Input() { calls++; return !fly; }
        void State(ref object state) { calls++; if (fly) state = 0; }
        object state = 2;
        GuardRules.ApplyState(false, ref state, State);
        Check((int)state == 2 && calls == 0, "NPC falling result must survive without invoking upstream.");
        Check(GuardRules.InputAllowed(false, Input) && calls == 0, "NPC input must continue while player flies.");
        GuardRules.ApplyState(true, ref state, State);
        Check((int)state == 0 && calls == 1, "Player Fly Mode must retain upstream state override.");
        Check(!GuardRules.InputAllowed(true, Input), "Player Fly Mode must retain upstream input suppression.");
        fly = false; state = 2;
        GuardRules.ApplyState(true, ref state, State);
        Check((int)state == 2 && GuardRules.InputAllowed(true, Input), "Player normal mode must remain normal.");

        var sample = new HoverObservation();
        Check(!sample.Observe(0, 100, 90, 0, true), "One stationary sample is insufficient.");
        Check(ObserveFor(sample, 0), "Persistent unsupported hover must qualify after six game seconds.");
        Check(!ObserveFor(sample, 7, clearance: 0), "Grounded recovered zombie must not qualify again.");
        Check(!ObserveFor(sample, 14, velocity: -5), "A falling zombie must not be teleported.");
        Check(!ObserveFor(sample, 21, velocity: 5), "A rising zombie must not be teleported.");
        Check(!ObserveFor(sample, 28, eligible: false), "Ragdoll, missing terrain or inactive physics must be excluded.");
        Check(!ObserveFor(sample, 35, height: float.NaN), "Invalid position must be excluded.");
        Check(!ObserveFor(sample, 42, clearance: float.PositiveInfinity), "Invalid ground result must be excluded.");
        sample.Reset();
        for (int i = 0; i < 50; i++) Check(!sample.Observe(50, 100, 90, 0, true), "Paused time must not qualify.");
        Check(!sample.Observe(100, 100, 90, 0, true), "A sampling gap must reset observation.");
        Check(!sample.Observe(1, 100, 90, 0, true), "Reloaded clock must reset observation.");
        Check(ObserveFor(sample, 1), "Fresh observation should qualify normally.");
        Check(!sample.Observe(7.5f, 99, 90, 0, true), "Position reset by another system must restart observation.");
        sample.Reset();
        Check(!sample.Observe(8, 99, 90, 0, true), "Explicit save/origin reset must discard qualification.");
        CheckDiagnostics();
        Console.WriteLine($"PASS: {assertions} assertions covering patch identity, player/NPC isolation, recovery rules and complete diagnostic reports.");
        return 0;
    }

    static void CheckDiagnostics()
    {
        // Regression shape from the actual 0.1.1 report: counters survived but rows were omitted.
        bool rejected = false;
        try { DiagnosticJson.ReadReport("{\"zombies\":127,\"unsupported\":13}"); }
        catch (SerializationException) { rejected = true; }
        Check(rejected, "A summary-only report must be rejected instead of silently losing evidence.");
        var row = new Row { id = 17, name = "zombie \"example\"", worldPosition = new Point(1, 120, 3),
            velocity = new Point(0, -2, 0), exclusion = "ragdoll/fallen state", observation = "excluded by controller/ground state",
            fallen = true, trace = new TraceSample { fixedCalls = 12, antiFallCalls = 4, antiFallMoves = 3, lastAntiFallAfterY = 120 } };
        var report = new Report { zombies = 1, unsupported = 1, rows = new[] { row } };
        string serialized = DiagnosticJson.CompleteReport(report);
        // Independent parser catches missing arrays/fields and validates escaping and nested values.
        using (var parsed = JsonDocument.Parse(serialized))
        {
            var rows = parsed.RootElement.GetProperty("rows");
            Check(rows.GetArrayLength() == 1, "The per-zombie row must be present.");
            Check(rows[0].GetProperty("name").GetString() == row.name, "Diagnostic strings must be correctly escaped.");
            Check(rows[0].GetProperty("worldPosition").GetProperty("y").GetSingle() == 120, "World height must survive serialization.");
            Check(rows[0].GetProperty("trace").GetProperty("antiFallMoves").GetInt32() == 3, "Nested controller trace must survive serialization.");
            Check(rows[0].GetProperty("exclusion").GetString() == row.exclusion, "Repair exclusion must be inspectable.");
        }
        rejected = false;
        try { DiagnosticJson.CompleteReport(new Report { zombies = 2, rows = new[] { row } }); }
        catch (SerializationException) { rejected = true; }
        Check(rejected, "Incorrect row counts must be rejected on the runtime write path.");
        using (var parsed = JsonDocument.Parse(DiagnosticJson.Serialize(new RecoveryEvent { before = row, target = new Point(1, 2, 3) })))
            Check(parsed.RootElement.GetProperty("before").GetProperty("id").GetInt32() == 17, "Write-ahead repair record must contain the full before state.");

        string folder = Path.Combine(Path.GetTempPath(), "AdminPanelFlyModeFix-check-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        try
        {
            DiagnosticJson.WriteReport(folder, report);
            DiagnosticJson.WriteReport(folder, new Report { zombies = 0, rows = Array.Empty<Row>() });
            Check(DiagnosticJson.ReadReport(File.ReadAllText(Path.Combine(folder, "latest.json"))).zombies == 0, "Repeated report writes must replace the current snapshot.");
            Check(File.ReadAllLines(Path.Combine(folder, "history.jsonl")).Length == 2, "Successive observations must remain available for comparison.");
            Check(!File.Exists(Path.Combine(folder, "latest.json.tmp")), "Successful replacement must not leave a partial snapshot.");
        }
        finally
        {
            foreach (string name in new[] { "latest.json", "latest.json.tmp", "history.jsonl" })
            {
                string path = Path.Combine(folder, name);
                if (File.Exists(path)) File.Delete(path);
            }
            Directory.Delete(folder);
        }
    }
}
