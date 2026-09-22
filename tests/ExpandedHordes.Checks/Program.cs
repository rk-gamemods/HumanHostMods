using System;
using System.IO;
using System.Linq;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.Emit;
using System.Reflection.PortableExecutable;
using ExpandedHordes;

internal static class Program
{
    private static int assertions;
    private static void Check(bool condition, string message)
    {
        assertions++;
        if (!condition) throw new Exception(message);
    }

    private static void Main(string[] args)
    {
        Check(CombatRules.ResistLoss(100, 60, 50) == 80, "50% resistance halves 40 incoming damage");
        Check(CombatRules.ResistLoss(100, 60, 0) == 60, "Zero resistance preserves damage");
        Check(CombatRules.ResistLoss(100, -300, 50) == -100, "Reduced overkill remains lethal before native clamp");
        Check(CombatRules.ResistLoss(100, 0, 50) == 50, "Lethal raw hit can be survived after resistance");
        Check(CombatRules.ResistLoss(20, 100, 95) == 100, "Healing/reset-to-full is untouched");
        Check(CombatRules.ResistLoss(0, -20, 50) == -20, "Dead bodies are untouched");
        Check(CombatRules.ResistLoss(100, 0, 95) == 95, "Maximum allowed resistance still permits damage");
        Check(CombatRules.ResistLoss(100, 100, 50) == 100, "Repeated identical HP assignment is idempotent");
        Check(float.IsNaN(CombatRules.ResistLoss(100, float.NaN, 50)), "Invalid native health is not hidden");
        Check(CombatRules.Classify(true, ZombieKind.Regular) == ZombieKind.Boss, "New native/mod boss flags are recognized");
        Check(CombatRules.Classify(false, ZombieKind.Large) == ZombieKind.Large, "Known large remains separate");
        Check(CombatRules.Classify(false, ZombieKind.Regular) == ZombieKind.Regular, "Unknown non-boss uses regular settings");
        Check(CombatRules.CorpseCapacity(50, 300) == 300, "Default retains up to vanilla menu maximum");
        Check(CombatRules.CorpseCapacity(300, 2000) == 2000, "Optional higher corpse capacity");
        Check(CombatRules.CorpseCapacity(6000, 300) == 6000, "Another mod's higher limit is retained");
        var frames = new FrameWindow();
        Check(frames.Percentile95() == 0, "Empty profile window");
        for (int i = 1; i <= 100; i++) frames.Add(i);
        Check(frames.Count == 100 && frames.Mean == 50.5 && frames.Percentile95() == 95 && frames.Maximum == 100, "Frame summary known distribution");
        frames.Reset();
        frames.Add(double.NaN); frames.Add(double.PositiveInfinity); frames.Add(0);
        Check(frames.Count == 0, "Invalid profiler samples excluded");
        for (int i = 0; i < 10000; i++) frames.Add(10);
        Check(frames.Count == 10000 && frames.SampleCount == 8192 && frames.Mean == 10 && frames.Percentile95() == 10, "Profiler storage bounded without losing average count");
        Check(PerformanceRules.Hint(20, 0, 0, 25) == "unavailable", "Missing GPU data must not imply CPU bottleneck");
        Check(PerformanceRules.Hint(20, 5, 0, 25) == "CPU_heavier", "CPU-heavy indication");
        Check(PerformanceRules.Hint(5, 20, 0, 25) == "GPU_heavier", "GPU-heavy indication");
        Check(PerformanceRules.Hint(5, 6, 5, 20) == "presentation_limit_suspected", "Wait-dominated indication");
        Check(HordeRules.Budget(1000, 0.2f) == 200, "Vanilla 20% lowers total");
        Check(HordeRules.Budget(1000, 1f) == 1000, "Vanilla 100% preserves base total");
        Check(HordeRules.Budget(1000, 8f) == 8000, "Vanilla 800% multiplies total");
        Check(HordeRules.Budget(50000, 8f) == 400000, "50,000 base maximum applies BEFORE multiplication");
        Check(HordeRules.Budget(50000, 0.2f) == 10000, "Lower percentage still lowers maximum base");
        Check(HordeRules.Budget(15, 0.5f) == 8, "Round like vanilla");
        Check(HordeRules.Budget(1, 0.2f) == 0, "Tiny scaled budget can round to zero");
        foreach (float invalid in new[] { 0f, -1f, float.NaN, float.PositiveInfinity })
            Check(HordeRules.Budget(1000, invalid) == 0, "Invalid quantity disables spawns");
        Check(HordeRules.Remaining(HordeRules.Budget(1000, 8f), 1000) == 7000, "Reload subtracts prior spawns from scaled total");
        Check(HordeRules.Remaining(50000, 0) == 50000, "Maximum finite budget");

        Check(HordeRules.RunSpeedMultiplier(125, true, false, 2, true, true) == 1.25f, "Horde run boost");
        Check(HordeRules.RunSpeedMultiplier(50, true, false, 2, true, true) == 0.5f, "Slower running is configurable");
        Check(HordeRules.RunSpeedMultiplier(100, true, false, 2, true, true) == 1f, "100% keeps native speed");
        Check(HordeRules.RunSpeedMultiplier(125, false, false, 2, true, true) == 1f, "Budget exhaustion or ordinary night restores speed");
        Check(HordeRules.RunSpeedMultiplier(125, true, true, 2, true, true) == 1f, "Dawn restores speed before native coroutine polling");
        Check(HordeRules.RunSpeedMultiplier(125, true, false, 1, true, true) == 1f, "Ambient zombies stay normal");
        Check(HordeRules.RunSpeedMultiplier(125, true, false, 2, false, true) == 1f, "Walking stays normal");
        Check(HordeRules.RunSpeedMultiplier(125, true, false, 2, true, false) == 1f, "Attacks and other animations stay normal");
        Check(HordeRules.Remaining(1000, 999) == 1, "Last replacement");
        Check(HordeRules.Remaining(1000, 1000) == 0, "Exhausted budget");
        Check(HordeRules.Remaining(1000, int.MaxValue) == 0, "Lowered budget on reload must not wrap");
        Check(HordeRules.Remaining(1000, 300) == 700, "Saved emitted count consumes the configured budget");
        foreach (int target in new[] { 1, 75, 60, 999, 1000 })
            foreach (float multiplier in new[] { 0.125f, 0.5f, 1f, 1.5f, 8f, 100f })
            {
                int native = (int)Math.Round(HordeRules.PioneerBase(target, multiplier) * multiplier);
                Check(Math.Min(native, target) == target, $"Native multiplier {multiplier} must preserve target {target}");
            }
        Check(HordeRules.Region(0, 0, 1024, 1024) == 1, "Origin is first region");
        Check(HordeRules.Region(10240, 0, 1024, 1024) == 10, "Native offset before repeating cycle");
        Check(HordeRules.Region(11264, 0, 1024, 1024) == 11, "Second cycle begins at region 11");
        Check(HordeRules.Region(-11264, 0, 1024, 1024) == 11, "Region is radial");
        Check(HordeRules.Region(21504, 0, 1024, 1024) == 21, "Region must not wrap with biome type");
        Check(HordeRules.Region(20480, 0, 1024, 2048) == 10, "Installed two-grid biome width before gate");
        Check(HordeRules.Region(21504, 0, 1024, 2048) == 11, "Installed two-grid biome width after gate");
        foreach (int region in new[] { 1, 10, 11, 12 })
        {
            int[] counts = new int[3];
            for (int roll = 0; roll < 100; roll++)
                counts[HordeRules.Category(roll, region, 11, 12, 20, 5)]++;
            Check(counts[1] == (region >= 11 ? 20 : 0), "Independent large gate and percentage");
            Check(counts[2] == (region >= 12 ? 5 : 0), "Independent boss gate and percentage");
            Check(counts[0] + counts[1] + counts[2] == 100, "All slots accounted for");
        }
        for (int roll = 0; roll < 100; roll++)
            Check(HordeRules.Category(roll, 11, 11, 11, 0, 0) == 0, "Zero percentages retain vanilla");
        Check(HordeRules.Category(79, 11, 11, 11, 40, 40) == 1, "Maximum extra chances cover 80 slots");
        Check(HordeRules.Category(80, 11, 11, 11, 40, 40) == 0, "Maximum chances leave 20 native slots");

        if (args.Length != 1) throw new ArgumentException("Pass the installed game's Managed directory for contract checks.");
        using (var dll = new AssemblyContract(Path.Combine(args[0], "Terrain.dll")))
        {
            dll.Method("NPC_Horde_Mgr", "_Start");
            dll.Method("NPC_Horde_Mgr", "Get_Plan_To_Spawn_Count");
            dll.Method("NPC_Horde_Mgr", "StartHordeEvent", "isLoad");
            dll.Method("NPC_Horde_Mgr", "Spawn_Horde_NPC", "biomeIndex", "groupIndex", "mutantLevel", "npcPrefabIndex", "spawnPosWorld", "euler", "async");
            dll.Method("NPC_Horde_Mgr", "GetValidSpawnPosition", "startPos", "minSpawnDis", "spawnRadius", "maxAttempts");
            dll.Method("NPC_Horde_Mgr", "Try_Get_Spawn_Context", "bioInfo");
            dll.Method("NPC_Horde_Mgr", "Save_Horde_Data_To_Disk");
            dll.Fields("NPC_Horde_Mgr", "_hordeSaveData", "_HordeZombieAll", "_ZombiesPioneerCount", "_ZombiesPerWaveAdd", "_MaxAllowActiveZombies", "_corHordeSpawn");
            dll.Fields("NPC_Spawner_Mgr", "NPC_Biomes");
            dll.Fields("Terrain_Loader_Manager", "BigTerraWidth");
        }
        using (var dll = new AssemblyContract(Path.Combine(args[0], "AI.dll")))
        {
            dll.Method("Zombie_Agent", "_Update");
            dll.Method("AI_Agen_Mgr", "MyStart");
            dll.Method("AI_Agen_Mgr", "SetHorde_MaxAllowActiveZombies");
            dll.Fields("AI_Agen_Mgr", "_InWaitSorting", "_MaxAllowActiveZombies");
        }
        using (var dll = new AssemblyContract(Path.Combine(args[0], "Creature.dll")))
        {
            dll.Method("Char_Status", "set__CurrHP", "value");
            dll.Fields("Char_Status", "_Controller");
            dll.Method("GPUI_Dead_Body_Mgr", "Spawn_GPUI_Dead_Body", "body_Disk", "bioIndex", "bodyPrefabIndex", "groupIndex", "hasHead", "bodyPos", "spineToHeadDirect", "charForward", "ragdollMgr", "bloodDecalIns", "onTerraOrOnBI", "belongKey");
            dll.FieldReads("GPUI_Dead_Body_Mgr", "Spawn_GPUI_Dead_Body", "_MaxCorpseCount", 1);
            dll.Fields("GPUI_Dead_Body_Mgr", "_ActiveDeadBodies");
            dll.Method("C_Controller_Base", "Play_Anim_BaseLayer", "clip", "clipTran", "transitionTime", "speed");
            dll.Fields("C_Controller_Base", "curr_Move_F", "Pressed_FastMove", "Pressed_Move", "currCharState");
            dll.Fields("NPC_Input", "_npcSpawnSource", "_inRunning");
            dll.Fields("Creature_Mgr", "_IsDayTime");
        }
        Console.WriteLine($"PASS: {assertions} policy and installed-assembly contract assertions. Unity runtime behavior is not tested here.");
    }

    // Read metadata without loading Unity or invoking the game.
    private sealed class AssemblyContract : IDisposable
    {
        private readonly FileStream stream;
        private readonly PEReader pe;
        private readonly MetadataReader reader;
        internal AssemblyContract(string path)
        {
            stream = File.OpenRead(path);
            pe = new PEReader(stream);
            reader = pe.GetMetadataReader();
        }
        private TypeDefinition Type(string name) => reader.TypeDefinitions.Select(reader.GetTypeDefinition)
            .Single(t => reader.GetString(t.Name) == name);
        internal void Method(string type, string name, params string[] parameters)
        {
            var matches = Type(type).GetMethods().Select(reader.GetMethodDefinition)
                .Where(m => reader.GetString(m.Name) == name).ToArray();
            Check(matches.Length == 1, $"Unique patch target {type}.{name}");
            var actual = matches[0].GetParameters().Select(reader.GetParameter).Where(p => p.SequenceNumber != 0)
                .Select(p => reader.GetString(p.Name));
            Check(actual.SequenceEqual(parameters), $"Patch argument names: {type}.{name}");
        }
        internal void Fields(string type, params string[] names)
        {
            var actual = Type(type).GetFields().Select(reader.GetFieldDefinition).Select(f => reader.GetString(f.Name)).ToHashSet();
            foreach (string name in names) Check(actual.Contains(name), $"Field injection: {type}.{name}");
        }
        internal void FieldReads(string type, string methodName, string fieldName, int expected)
        {
            var method = Type(type).GetMethods().Select(reader.GetMethodDefinition)
                .Single(m => reader.GetString(m.Name) == methodName);
            byte[] il = pe.GetMethodBody(method.RelativeVirtualAddress).GetILBytes();
            var codes = typeof(OpCodes).GetFields().Where(f => f.FieldType == typeof(OpCode))
                .Select(f => (OpCode)f.GetValue(null)).ToDictionary(o => unchecked((ushort)o.Value));
            int offset = 0, count = 0;
            while (offset < il.Length)
            {
                ushort key = il[offset++];
                if (key == 0xfe) key = (ushort)(0xfe00 | il[offset++]);
                OpCode code = codes[key];
                if (code == OpCodes.Ldfld)
                {
                    var handle = MetadataTokens.EntityHandle(BitConverter.ToInt32(il, offset));
                    string name = handle.Kind == HandleKind.MemberReference
                        ? reader.GetString(reader.GetMemberReference((MemberReferenceHandle)handle).Name)
                        : reader.GetString(reader.GetFieldDefinition((FieldDefinitionHandle)handle).Name);
                    if (name == fieldName) count++;
                }
                offset += code.OperandType switch
                {
                    OperandType.InlineNone => 0,
                    OperandType.ShortInlineBrTarget or OperandType.ShortInlineI or OperandType.ShortInlineVar => 1,
                    OperandType.InlineVar => 2,
                    OperandType.InlineI8 or OperandType.InlineR => 8,
                    OperandType.InlineSwitch => 4 + 4 * BitConverter.ToInt32(il, offset),
                    _ => 4
                };
            }
            Check(count == expected, $"Verified narrow IL seam: {type}.{methodName} reads {fieldName} {expected} time(s)");
        }
        public void Dispose() { pe.Dispose(); stream.Dispose(); }
    }
}
