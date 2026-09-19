# Human Host mods

BepInEx 5 plugins for [Human Host](https://store.steampowered.com/app/2393970/),
plus the scripts used to set up, build and inspect them.

## Requirements

- Human Host (Steam)
- Windows, PowerShell 7
- .NET SDK 8 or later. ilspycmd 10 and later need the .NET 10 runtime.
- ilspycmd: `dotnet tool install -g ilspycmd`

## First-time setup

```powershell
.\tools\Install-BepInEx.ps1        # BepInEx 5, newest stable, into the game folder
# Launch the game once and quit, so BepInEx creates its config and log.
.\tools\Install-UnityExplorer.ps1  # optional in-game inspector, F7 to toggle
.\tools\Decompile-GameCode.ps1     # game code for reference, into HumanHostCodebase\
.\tools\Get-ModEnvStatus.ps1       # check everything is in place
```

If the game is not at `C:\Steam\steamapps\common\Human Host`, copy
`GamePaths.local.props.example` to `GamePaths.local.props` and set `HumanHostDir`.

## Building

```powershell
dotnet build HumanHostMods.slnx -c Release
dotnet build mods\HelloHost -c Release -p:DeployToGame=true   # also copies into BepInEx\plugins
```

Close the game before deploying. A loaded plugin DLL is locked.

## New mod

Copy `mods/HelloHost`, rename the folder and `.csproj`, update `AssemblyName`,
`RootNamespace` and the constants in `Plugin.cs`, then add the project to
`HumanHostMods.slnx`. Reference more game assemblies with
`<HumanHostRef Include="Player" />`.

## Layout

| Path | Contents |
| --- | --- |
| `mods/` | One folder per plugin |
| `tools/` | Setup, decompile and status scripts |
| `docs/` | Environment notes |
| `research/` | Findings about game code |
| `HumanHostCodebase/` | Decompiled game code (local only, gitignored) |

Decompiled code and game files are never committed.
