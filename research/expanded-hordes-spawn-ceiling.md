# Hypothetical maximum horde spawns

Requested by the user while selecting Expanded Hordes limits. This is an
idealized arithmetic ceiling, not a claim about playable population, kill rate
or game performance. No benchmark or game launch was performed.

## Inputs from the installed build

Steam build 25448142; source revision
`75505302bbe546b6f783690e4d97230c537edda0`:

- The actual world-settings slider allows **60-240 real minutes per game day**.
  `G_Save`'s editor attribute says 5-1,440, but that is not the player's menu
  range. `G_Config_Setter._Game24H_S` in `level0` supplies the menu limits.
- The separate daylight proportion slider allows **20%-80%**, default 70%.
  `Weather_Controller.Set_Time_Pass_Parameter` sets the night duration factor
  to `2 * (1 - daylight proportion)`, hence at most **1.6**.
- The serialized world's `NPC_Horde_Mgr._HordeIntervalHours` is **1-6**,
  overriding the source initializer of 4-8. Relative to 19:00, the earliest
  start is **20:00**. `Creature_Mgr.Is_Day_Time` ends night at **06:30**.
- `NPC_Horde_Mgr.Spawn_Horde_NPCs` spawns serially, waits for each asynchronous
  factory call and then waits **0.1 scaled seconds**. With all other costs
  assumed zero, that is **10 spawns per second**. The starting population is
  generated through this same loop; it is not a separate instantaneous batch.
- `EnviroTimeModule.UpdateModule` advances the clock using
  `1440 / (cycleLengthInMinutes * current day/night duration factor)`.
  `EnviroManager.UpdateManager` selects the factor using its solar day/night
  state. That transition is not guaranteed to coincide with the horde's fixed
  06:30 end, so applying the slowest factor to the whole interval is a
  conservative upper-bound assumption, not an exact measured night duration.

Serialized evidence was extracted read-only using
`.local/expanded-hordes/timing_limits.py`, producing `timing-limits.json`.
The two Enviro types were decompiled locally under `.local/expanded-hordes/enviro`.
These game-derived files remain gitignored.

## Wolfram calculation

Assume earliest start, maximum 240-minute day duration, the slowest allowed
clock rate throughout the entire horde window, normal time scale, immediate
kills and zero placement/loading/frame overhead:

```text
Game-clock window: (24 - 20) + 6.5 = 10.5 hours
Real seconds:     (10.5 / 24) * 240 * 60 * 1.6 = 10,080
Real minutes:     10,080 / 60 = 168
Ideal spawns:     10,080 / 0.1 = 100,800
```

The connected Wolfram Language evaluator returned 10,080 seconds, 168 minutes
and 100,800 spawns for daylight fraction `1/5`. Reproducible expression:

```wolfram
dayMinutes = 240;
hordeHours = (24 - 20) + 6.5;
seconds = hordeHours/24 * dayMinutes * 60 * 2*(1 - 1/5);
{seconds, seconds/60, seconds*10}
```

The **200-alive limit does not bind** when every spawn is killed immediately.
It does not multiply the spawn rate by 200. Real spawning is slower because
the factory, valid placement and frame scheduling consume time. Native dawn
polling and an in-flight spawn can add a small tail, so 100,800 is a rounded
idealized estimate, not a strict exact integer bound including that tail.

The budget is an independent limit: a base of 1,000 at 800% stops at 8,000
creations, while the maximum base of 50,000 at 800% permits 400,000 but does not
provide enough time to reach it under this estimate. No claim is made that a
player could sustain ten kills per second or that the game could sustain the
assumed spawning, corpses or combat load.
