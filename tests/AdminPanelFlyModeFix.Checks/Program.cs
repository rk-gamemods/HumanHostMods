using System;
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

    static void Main()
    {
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
        Console.WriteLine($"PASS: {assertions} assertions covering patch identity, player/NPC isolation, pause/reload, falling and repeated recovery.");
    }
}
