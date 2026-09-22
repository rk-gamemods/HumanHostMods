# Publish Expanded Hordes after play testing

This folder is a prepared release candidate, not a published or runtime-certified
release. Finish `PLAYTEST.md` before uploading. No account credentials or Workshop
item ID have been supplied, and no upload has been attempted.

## Contents

- `content/ExpandedHordes/`: the complete Workshop payload. Only the original
  plugin DLL and player README are installed. The game's Workshop installer
  copies this layout beneath `BepInEx/plugins/`.
- `ExpandedHordes-0.2.0.zip`: the same payload for manual distribution. Extract
  beneath `BepInEx/plugins/`, with the game closed.
- `preview.png`: original 1,024-square title graphic; no game artwork.
- `workshop-description.txt`: ready-to-paste Steam BBCode description.
- `workshop.vdf`: optional SteamCMD upload manifest, private by default, using
  absolute paths on this machine. Rebuild it if the release directory moves.
- `sample.cfg`: reference defaults only. It is excluded from the payload to
  avoid overwriting anyone's settings.
- `SHA256SUMS.txt`, `build-info.json`: package file hashes and build provenance.

Build or refresh from the repository root:

```powershell
pwsh -NoProfile -File tools/Package-ExpandedHordes.ps1
```

The script builds, runs policy/installed-assembly checks, generates a fresh
sample config, checks the payload allowlist and hashes the release. It never
uploads, launches the game or modifies live config. It preserves an existing
`publishedfileid` in the local VDF; after a first upload, retain that updated
VDF for future releases so an update does not create a duplicate item.

## Game's built-in Workshop uploader

1. After successful testing, open Human Host's Workshop upload interface.
2. Select this release's **content** folder. Do not select the whole release
   folder, its nested ExpandedHordes folder, or BepInEx itself.
3. Use title **Expanded Hordes**, paste `workshop-description.txt`, and select
   `preview.png`. Review the account, description and visibility before submission.
4. Submit only when ready to publish. The inspected game's new-item uploader
   explicitly requests **public** visibility; it is not a private staging flow.
5. Complete any Steam Workshop agreement/account requirements. Record the item
   URL/ID. Test its downloaded installation with the local copy disabled.

## Optional private staging through SteamCMD

Valve documents the following upload command. SteamCMD/account access and this
game's acceptance of that route have not been tested here. The game's built-in
uploader above is the inspected native publishing path.

```text
steamcmd +login YOUR_ACCOUNT +workshop_build_item "ABSOLUTE_PATH_TO/workshop.vdf" +quit
```

Log in interactively; do not put passwords in repository files. The generated
manifest sets visibility to private (`2`) and uses item ID `0` until the first
upload. SteamCMD writes the resulting item ID back into the VDF. For an item
created through the game, set that existing ID in the VDF before any later
SteamCMD update. Reuse the same item rather than creating duplicates. Inspect
the uploaded files/page before changing visibility to public in Steam.

Sources: the installed game's `Workshop_UI.UploadNewModFlow` and
`ModBrowserBridge` download/copy flow; [Human Host Workshop](https://steamcommunity.com/app/2393970/workshop/?l=english);
[Valve Workshop implementation and SteamCMD upload format](https://partner.steamgames.com/doc/features/workshop/implementation?l=english).

## Support and future updates

Ask bug reports to include the game build, mod version, settings, other mods,
reproduction steps and relevant BepInEx log; add the optional profiling CSV for
performance reports. No safe maximum or FPS improvement is advertised.

After a game update, recheck the patched members and creature identities,
rebuild, rerun the release checks and repeat affected runtime tests. See the
repository's `docs/expanded-hordes-maintenance.md`. Keep game assemblies,
decompiled game code, save files, logs and user configs out of the payload.
