<#
.SYNOPSIS
    Installs or upgrades BepInEx 5 (win x64) in the Human Host install folder.

.DESCRIPTION
    Downloads BepInEx_win_x64_<version>.zip from github.com/BepInEx/BepInEx and
    extracts it next to "Human Host.exe". Before overwriting, every file the zip
    would replace is copied to .local\backups\ in this repository.

    The zip holds only winhttp.dll, doorstop_config.ini, .doorstop_version,
    changelog.txt and BepInEx\core\. Plugins, configs and patchers are not touched.

    Human Host is a Unity Mono game, so it uses BepInEx 5, not the BepInEx 6
    pre-releases.

.EXAMPLE
    .\tools\Install-BepInEx.ps1                  # newest stable 5.x
    .\tools\Install-BepInEx.ps1 -Version 5.4.23.5
    .\tools\Install-BepInEx.ps1 -WhatIf          # show what would change
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$Version,
    [string]$GameDir,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\Common.ps1"

$GameDir = Resolve-HumanHostDir -GameDir $GameDir
Assert-HumanHostClosed

$release = if ($Version) {
    Get-GitHubRelease -Repo 'BepInEx/BepInEx' -Tag "v$($Version.TrimStart('v'))"
} else {
    Get-GitHubRelease -Repo 'BepInEx/BepInEx' -TagPattern '^v5\.'
}
$target = $release.tag_name.TrimStart('v')
$installed = Get-InstalledBepInExVersion -GameDir $GameDir

Write-Host "Game folder: $GameDir"
Write-Host "Installed:   $(if ($installed) { $installed } else { 'none' })"
Write-Host "Target:      $target"

if ($installed -eq $target -and -not $Force) {
    Write-Host 'BepInEx is already at the target version. Use -Force to reinstall.'
    return
}

$zip = Save-ReleaseAsset -Release $release -AssetName "BepInEx_win_x64_$target.zip"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [IO.Compression.ZipFile]::OpenRead($zip)
try {
    $entries = $archive.Entries | Where-Object { $_.Name } | ForEach-Object { $_.FullName }
} finally {
    $archive.Dispose()
}

$existing = $entries | Where-Object { Test-Path (Join-Path $GameDir $_) }
if ($existing) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backup = Join-Path $script:RepoRoot ".local\backups\bepinex-$(if ($installed) { $installed } else { 'unknown' })-$stamp"
    if ($PSCmdlet.ShouldProcess($backup, "Back up $($existing.Count) files")) {
        foreach ($rel in $existing) {
            $dest = Join-Path $backup $rel
            New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
            Copy-Item -LiteralPath (Join-Path $GameDir $rel) -Destination $dest
        }
        Write-Host "Backed up $($existing.Count) files to $backup"
    }
}

if ($PSCmdlet.ShouldProcess($GameDir, "Extract BepInEx $target")) {
    Expand-Archive -LiteralPath $zip -DestinationPath $GameDir -Force
    $now = Get-InstalledBepInExVersion -GameDir $GameDir
    Write-Host "BepInEx core now reports $now."
    if ($now -ne $target) { throw "Expected $target after extraction, found $now." }
    Write-Host 'Launch the game once, then run tools\Get-ModEnvStatus.ps1 to confirm it loaded.'
}
