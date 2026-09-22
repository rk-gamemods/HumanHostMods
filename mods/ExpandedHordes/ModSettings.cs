using BepInEx.Configuration;

namespace ExpandedHordes
{
    // One binding definition for the plugin and pre-launch local installation.
    internal static class ModSettings
    {
        internal static ConfigEntry<int> Total, Living, Allowance, LargeBegin, BossBegin, LargePercent, BossPercent, RunSpeedPercent;
        internal static ConfigEntry<float> AttractionHeight, AttractionRadius;
        internal static ConfigEntry<int> RegularResistance, LargeResistance, BossResistance, CorpseLimit;
        internal static ConfigEntry<bool> DebugMode, Profiling;

        internal static void Bind(ConfigFile config)
        {
            RegularResistance = BindResistance(config, "Regular Zombie Resistance", 25);
            LargeResistance = BindResistance(config, "Large Zombie Resistance", 40);
            BossResistance = BindResistance(config, "Boss Resistance", 50);
            CorpseLimit = BindInt(config, "Corpses", "Retained Corpse Limit", 300, 1, 5000,
                "How many nearby settled corpses the game's normal cleanup tries to retain. Default: 300, matching the vanilla menu's maximum. A higher limit keeps more bodies visible; it can reduce FPS and increase memory/save size. The higher of this setting and the game's current limit is used, so another mod's higher limit is respected. This affects the shared corpse pool, including ordinary zombies. Old corpses are removed to make room; corpses do not block new living horde spawns. Native expiry and distance cleanup still apply. This does not keep physical ragdolls active forever or guarantee stacked collision piles. The upper setting of 5,000 is untested.");
            DebugMode = config.Bind("Diagnostics", "Debug Mode", false,
                "Write extra event, placement and compatibility details to BepInEx/LogOutput.log. Default: off. Errors and feature-disable warnings are always logged. Summaries are limited to avoid a line for every zombie or hit. Restart after changing settings.");
            Profiling = config.Bind("Diagnostics", "Performance Profiling", false,
                "Collect frame times, available CPU/GPU timings, managed memory, garbage-collection counts and selected zombie/placement/corpse/mod timings. Default: off. Writes a summary every 15 seconds and a bounded performance.csv beside this mod's DLL. Missing GPU/CPU measurements are shown as unavailable; bottleneck hints are not proof of a cause. Profiling adds overhead. It does not change game graphics settings or require a separate profiler mod. Restart after changing settings.");
            Total = BindInt(config, "Population", "Total Spawn Budget", 1000, 1, 50000,
                "Base number of zombies one horde can create, including replacements after kills. The game's Horde Quantity percentage multiplies this number: a base of 1,000 allows 200 at 20%, 1,000 at 100%, or 8,000 at 800%. The 50,000 maximum applies BEFORE the multiplier, allowing a total budget of 400,000 at 800%. The final total is rounded to a whole number. Dawn stops new arrivals even if the total has not been reached. Vanilla starts at 15 at 100% or 120 at 800%, then adds 2 for each previous horde. This mod instead uses your chosen base times the game's percentage, without per-horde growth. Default base: 1,000. Allowed base: 1-50,000. Enter an exact value in the number box beside the slider. Very small bases with low percentages can round to zero. Horde frequency stays controlled by the game.");
            Living = BindInt(config, "Population", "Living Horde Target", 75, 1, 1000,
                "How many horde zombies can be alive at the same time. Kills make room for replacements until the total budget runs out or dawn arrives. Vanilla starts at 2 alive with Horde Quantity set to 100%, adds 1 for each previous horde, and stops at 60 alive. Example: Horde Quantity at 800%, horde 17 = 32 alive. This mod defaults to 75, above vanilla's 60 limit. Shared AI Allowance and the remaining total budget can reduce this number. Nearby ordinary zombies are extra. More zombies can reduce FPS.");
            Allowance = BindInt(config, "Population", "Shared AI Allowance", 90, 1, 1000,
                "How many loaded zombies the game allows to focus on targets when reacting to sounds. Vanilla: 60. Mod default: 90. Horde zombies and ordinary nearby zombies share this limit, even between hordes. Keep this at least as high as Living Horde Target; otherwise it also lowers that target. Raising it can make more zombies chase and fight, which can reduce FPS. No safe performance maximum has been measured.");
            RunSpeedPercent = BindInt(config, "Movement", "Horde Run Speed Percentage", 125, 25, 300,
                "Running speed of zombies spawned as part of a horde, while that horde is still spawning. 100% is each zombie type's normal running speed; 125% is 25% faster; 50% is half speed. Default: 125%. Normal speed returns when spawning finishes or dawn arrives, whichever comes first. Ordinary zombies attracted to the fight are unaffected. This does not make walking zombies run or speed up attacks. Normal nights and daytime are unaffected. Faster arrivals can make combat more demanding and may reduce FPS; performance has not been measured.");
            LargeBegin = BindInt(config, "Composition", "Extra Large Zombie Begin Biome", 11, 1, 1000000,
                "First biome region where this mod can add large zombies to a horde. Regions count outward from the starting area, including repeats: 11 begins the second cycle of ten biomes. Set 1 to allow extras from the starting region. Returning to an earlier region stops these extra choices. Large zombies that vanilla already includes are unaffected.");
            BossBegin = BindInt(config, "Composition", "Extra Boss Zombie Begin Biome", 11, 1, 1000000,
                "First biome region where this mod can add bosses to a horde. Regions count outward from the starting area, including repeats: 11 begins the second cycle of ten biomes. Set 1 to allow extras from the starting region. Returning to an earlier region stops these extra choices. Bosses that vanilla already includes are unaffected.");
            LargePercent = BindInt(config, "Composition", "Extra Large Zombie Percentage", 20, 0, 40,
                "For EACH new horde zombie, the percentage chance of spawning a large non-boss zombie instead of the game's normal choice. This includes the starting attackers and every replacement after a kill; it is not one chance per wave. At 20%, about 20 in every 100 new zombies are changed to a large type on average, once Extra Large Zombie Begin Biome is reached. Actual numbers vary. Vanilla may also choose large zombies among the unchanged spawns. Reloading saved zombies does not change their type.");
            BossPercent = BindInt(config, "Composition", "Extra Boss Zombie Percentage", 5, 0, 40,
                "For EACH new horde zombie, the percentage chance of spawning a boss instead of the game's normal choice. This includes the starting attackers and every replacement after a kill; it is not one chance per wave. At 5%, about 5 in every 100 new zombies are changed to a boss on average, once Extra Boss Zombie Begin Biome is reached. No boss is guaranteed in a small group. With 20% large and 5% boss, the other 75% use the normal choice, which can also include bosses. Reloading saved zombies does not change their type.");
            AttractionHeight = config.Bind("Attraction", "Elevated Sound Height", 100f,
                new ConfigDescription("At horde start, the mod tries to lure nearby zombies toward you as if you made a noise. It does this once at your head and once this many metres above it, to help the lure reach over walls and roofs. You hear no sound, and zombies still try to reach you on the ground. Vanilla has no such horde-start lure. Default: 100 metres above your head. Buildings can still block it. Hearing Radius measures distance from each lure, so raising the height uses up part of its reach. Maximum height: 100 metres.", new AcceptableValueRange<float>(0f, 100f)));
            AttractionRadius = config.Bind("Attraction", "Hearing Radius", 250f,
                new ConfigDescription("How far the one-time horde-start lure can reach, in metres from each of its two positions. It only attracts zombies already nearby; it never creates distant zombies or loads more of the map. Vanilla normally creates ordinary zombies 50-100 metres from you and removes them beyond 150 metres. The maximum here is 250 metres to cover those nearby zombies plus the lure up to 100 metres overhead. A million-metre radius would not attract zombies from an unloaded world. Height counts toward the distance. Walls, roofs and the shared zombie limit can still stop a response. Attracting more existing zombies can reduce FPS through chasing and fighting; the cost has not been measured.", new AcceptableValueRange<float>(1f, 250f)));
        }

        private static ConfigEntry<int> BindInt(ConfigFile config, string section, string key, int value, int min, int max, string description) =>
            config.Bind(section, key, value, new ConfigDescription(description, new AcceptableValueRange<int>(min, max)));

        private static ConfigEntry<int> BindResistance(ConfigFile config, string key, int value) =>
            BindInt(config, "Resistance", key, value, 0, 95,
                "Percentage of incoming health damage prevented for this category of horde-spawned zombie. 0% adds no resistance; 50% halves damage; 75% means one quarter gets through. Maximum health and health-based kill XP are unchanged. Ordinary zombies outside the horde are unaffected. Unlike run speed, this stays with surviving horde zombies after dawn and after save/load, using the current settings. Bosses use Boss Resistance; known large non-boss types use Large Zombie Resistance; other types use Regular Zombie Resistance. Covers native health-loss paths, including weapons and falling structures. Direct forced-death effects or mods bypassing native health handling may bypass it. The 95% maximum avoids invulnerability.");

    }
}
