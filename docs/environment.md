# Environment

State of the local modding setup, recorded 2026-09-19. Run
`tools/Get-ModEnvStatus.ps1` for the current state.

## Game

| Item | Value |
| --- | --- |
| Install | `C:\Steam\steamapps\common\Human Host` |
| Steam app / build | 2393970 / 25407931 |
| Game version | 0.8.311 (`Application.version`) |
| Engine | Unity 2022.3.62f3, Mono, HDRP |
| Managed assemblies | `Human Host_Data\Managed`, 294 DLLs, most with PDBs |

## Loader and tools

| Tool | Version | Location |
| --- | --- | --- |
| BepInEx | 5.4.23.5 | game folder (`winhttp.dll`, `doorstop_config.ini`, `BepInEx\`) |
| Doorstop | 4.5.0 | `.doorstop_version` in the game folder |
| UnityExplorer (yukieiji fork) | 4.13.6 | `BepInEx\plugins\sinai-dev-UnityExplorer\`, F7, hidden on startup |
| .NET SDK | 8.0.425, 10.0.401 | machine |
| ilspycmd | 11.0.0.9375 | global dotnet tool |

BepInEx was upgraded from 5.4.23.2 on 2026-09-19. 5.4.23.5 includes a fix for
Unity 2022.3.62f3 missing `get_graphicsDeviceID`. The replaced files are backed
up in `.local\backups\` (not committed).

## Third-party plugins in the install

Installed by the player through HHMM (Human Host Mod Manager), not by this
repository. Seen loading on 2026-09-19 (18 plugins with UnityExplorer and the
HelloHost test):

Admin Panel, ArmorTweaks, Backpack Expand, Human Host Explosives, Human Host
Suppressors, LightsaberPack, MapTweaks, Minest's Minimap, Mod Menu, Quick
Dismantle, Quick Loot, Quick Stack, Railgun Turrets, Repair Tweaks, Storage Box
Expand, Workbench Expand.

HHMM also installs `BepInEx\patchers\PendingFilePatcher.dll`. Leave these alone.

## Known log warnings from other mods

- HarmonyX: `Could not find field for type World_Map_Mgr and name _rightClicked` (MapTweaks)
- HarmonyX: `Could not find field for type CamController and name ins`
- Minest's Minimap: `main camera fallback to Camera.main`
