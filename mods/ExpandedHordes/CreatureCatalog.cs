using System;
using System.Collections.Generic;
using HarmonyLib;

namespace ExpandedHordes
{
    // Add native or mod-provided registered identities here. Selection and resistance
    // classification share this list; neither depends on runtime object names or HP.
    internal static class CreatureCatalog
    {
        internal readonly struct Definition
        {
            internal readonly string GroupGuid;
            internal readonly int Prefab;
            internal readonly ZombieKind Kind;
            internal Definition(string guid, int prefab, ZombieKind kind)
            { GroupGuid = guid; Prefab = prefab; Kind = kind; }
        }

        internal readonly struct Entry : IEquatable<Entry>
        {
            internal readonly int Biome, Group, Prefab;
            internal Entry(int biome, int group, int prefab) { Biome = biome; Group = group; Prefab = prefab; }
            public bool Equals(Entry other) => Biome == other.Biome && Group == other.Group && Prefab == other.Prefab;
            public override bool Equals(object obj) => obj is Entry other && Equals(other);
            public override int GetHashCode() => (Biome * 397 ^ Group) * 397 ^ Prefab;
        }

        private static readonly Definition[] Definitions =
        {
            new Definition("ec51da188d5daa748b95715295213311", 2, ZombieKind.Large), // Z_Man_Big_02
            new Definition("1fb724ba28e613143b5fe6dc62acb3ae", 0, ZombieKind.Large), // Z_Man_Big_01
            new Definition("b974c3cb8f07d2b4c86abed15ff9e6e2", 4, ZombieKind.Large), // Z_Man_Big_03
            new Definition("6048eb7135a0cda4a9c560cd2b875b6b", 3, ZombieKind.Boss), // Subject 1
            new Definition("1fd4a685d15c82b4b960f905c29e2e4a", 4, ZombieKind.Boss) // Artificial Mutant
        };
        private static readonly Dictionary<Entry, ZombieKind> Kinds = new Dictionary<Entry, ZombieKind>();
        private static AccessTools.FieldRef<NPC_Spawner_Mgr, NPC_Spawner_Mgr.NPC_Bio_Set[]> Biomes;
        internal static readonly List<Entry> Large = new List<Entry>();
        internal static readonly List<Entry> Bosses = new List<Entry>();

        internal static void Clear() { Kinds.Clear(); Large.Clear(); Bosses.Clear(); }

        internal static void Resolve(NPC_Spawner_Mgr manager)
        {
            Clear();
            if (!manager) throw new InvalidOperationException("Native creature registry is not available.");
            // Resolve inside the guarded setup, so an updated field cannot poison Clear().
            Biomes ??= AccessTools.FieldRefAccess<NPC_Spawner_Mgr, NPC_Spawner_Mgr.NPC_Bio_Set[]>("NPC_Biomes");
            var biomes = Biomes(manager);
            if (biomes == null) throw new InvalidOperationException("Native creature registry has no biome data.");
            foreach (var definition in Definitions)
            {
                bool added = false;
                for (int b = 0; b < biomes.Length; b++)
                {
                    var groups = biomes[b]?.groups;
                    if (groups == null) continue;
                    for (int g = 0; g < groups.Length; g++)
                    {
                        if (groups[g]?.npcBioSetRef?.AssetGUID != definition.GroupGuid) continue;
                        var entry = new Entry(b, g, definition.Prefab);
                        Kinds[entry] = definition.Kind;
                        // Classify every matching group, but select each creature only once.
                        if (!added)
                        {
                            (definition.Kind == ZombieKind.Boss ? Bosses : Large).Add(entry);
                            added = true;
                        }
                    }
                }
                if (!added) FeatureRuntime.WarnOnce("roster:" + definition.GroupGuid,
                    $"Extra creature group {definition.GroupGuid} is unavailable; skipped without replacing native choices.");
            }
            FeatureRuntime.DebugLog($"Creature catalog: {Large.Count} large types, {Bosses.Count} boss types resolved.");
        }

        internal static ZombieKind Classify(bool nativeBoss, NPC_Horde_Mgr.Horde_NPC_Info identity)
        {
            Kinds.TryGetValue(new Entry(identity.biomeIndex, identity.groupIndex, identity.npcPrefabIndex), out var kind);
            return CombatRules.Classify(nativeBoss, kind);
        }
    }
}
