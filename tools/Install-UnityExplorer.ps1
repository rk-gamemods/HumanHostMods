<#
.SYNOPSIS
    Installs or updates UnityExplorer (BepInEx 5, Mono build) into BepInEx\plugins.

.DESCRIPTION
    UnityExplorer is an in-game inspector for scenes, GameObjects, components and
    live field values, with a C# console. Toggle it in game with F7.

    Source: github.com/yukieiji/UnityExplorer, the maintained fork of
    sinai-dev/UnityExplorer. Installs to BepInEx\plugins\sinai-dev-UnityExplorer\.

.EXAMPLE
    .\tools\Install-UnityExplorer.ps1
    .\tools\Install-UnityExplorer.ps1 -Remove
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$GameDir,
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\Common.ps1"

$GameDir = Resolve-HumanHostDir -GameDir $GameDir
Assert-HumanHostClosed

$bepinex = Join-Path $GameDir 'BepInEx'
$pluginDir = Join-Path $bepinex 'plugins\sinai-dev-UnityExplorer'

if ($Remove) {
    if ((Test-Path $pluginDir) -and $PSCmdlet.ShouldProcess($pluginDir, 'Remove UnityExplorer')) {
        Remove-Item -LiteralPath $pluginDir -Recurse -Force
        Write-Host "Removed $pluginDir"
    }
    return
}

if (-not (Get-InstalledBepInExVersion -GameDir $GameDir)) {
    throw 'BepInEx is not installed. Run tools\Install-BepInEx.ps1 first.'
}

$release = Get-GitHubRelease -Repo 'yukieiji/UnityExplorer'
$zip = Save-ReleaseAsset -Release $release -AssetName 'UnityExplorer.BepInEx5.Mono.zip'

if ($PSCmdlet.ShouldProcess($bepinex, "Extract UnityExplorer $($release.tag_name)")) {
    # The zip's top-level folder is plugins\, so extract into BepInEx\.
    Expand-Archive -LiteralPath $zip -DestinationPath $bepinex -Force
    Write-Host "UnityExplorer $($release.tag_name) installed to $pluginDir. Press F7 in game to toggle it."
}

# UnityExplorer opens its UI and unlocks the mouse on every launch by default.
# Keep it hidden until F7. The config file only exists after the first launch.
$cfg = Join-Path $bepinex 'config\com.sinai.unityexplorer.cfg'
if ((Test-Path $cfg) -and $PSCmdlet.ShouldProcess($cfg, 'Set Hide On Startup = true')) {
    (Get-Content -Raw $cfg) -replace '(?m)^Hide On Startup = false', 'Hide On Startup = true' |
        Set-Content -NoNewline $cfg
} elseif (-not (Test-Path $cfg)) {
    Write-Host 'Launch the game once, then run this script again to hide UnityExplorer on startup.'
}
