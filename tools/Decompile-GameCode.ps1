#Requires -Version 7
<#
.SYNOPSIS
    Refreshes the local, text-only game source and serialized data catalog.
.DESCRIPTION
    Decompiles all non-framework managed assemblies, inventories installed inputs,
    exports serialized gameplay metadata, resolves references across bundles, and
    generates readable loot/item views. Media payloads are never exported.
    Stages and validates output before replacing the previous local Git snapshot.
    After capture (including unchanged capture), runs the configured wiki's
    deterministic update command and prints its final exception report.
    See docs/GAME_CODEBASE.md for dependencies, coverage and recovery.
#>
[CmdletBinding()]
param(
    [string]$GameDir,
    [string]$OutputPath,
    [string[]]$Assemblies,
    [switch]$All,
    [switch]$NoGit,
    [ValidateRange(1, 32)][int]$ThrottleLimit = 4,
    [string]$PythonPackagesPath,
    [string]$WikiPath,
    [switch]$SkipWiki
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\Common.ps1"
$GameDir = Resolve-HumanHostDir -GameDir $GameDir
if (-not $OutputPath) { $OutputPath = Join-Path $script:RepoRoot 'HumanHostCodebase' }
if (-not $PythonPackagesPath) {
    $localProps = Join-Path $script:RepoRoot 'GamePaths.local.props'
    if (Test-Path -LiteralPath $localProps) {
        $PythonPackagesPath = ([xml](Get-Content -Raw -LiteralPath $localProps)).Project.PropertyGroup.CatalogPythonPackages |
            Select-Object -First 1
    }
}
if (-not $PythonPackagesPath) {
    $defaultPackages = Join-Path $script:RepoRoot '.cache\catalog-python'
    if (Test-Path -LiteralPath $defaultPackages) { $PythonPackagesPath = $defaultPackages }
}
$arguments = @('-3', (Join-Path $PSScriptRoot 'game_catalog\refresh.py'), '--game', $GameDir,
    '--output', $OutputPath, '--workers', "$ThrottleLimit")
if ($PythonPackagesPath) { $arguments += @('--python-packages', $PythonPackagesPath) }
if ($Assemblies) { $arguments += '--assemblies'; $arguments += $Assemblies }
if ($NoGit) { $arguments += '--no-git' }
# -All remains accepted for existing callers. Full non-framework coverage is now the default.
& py @arguments
if ($LASTEXITCODE -ne 0) { throw "Game codebase refresh failed (exit $LASTEXITCODE)." }
if ($SkipWiki -or $NoGit -or $Assemblies) {
    Write-Host 'Wiki update skipped: source-only or partial diagnostic capture requested.'
    return
}
if (-not $WikiPath) { $WikiPath = Join-Path $script:RepoRoot 'HumanHostWiki' }
$wikiCommand = Join-Path $WikiPath 'wiki.py'
if (-not (Test-Path -LiteralPath $wikiCommand -PathType Leaf)) {
    throw "Capture completed, but the wiki command is missing: $wikiCommand. Configure -WikiPath or use -SkipWiki for source-only work."
}
& py -3 $wikiCommand update --source $OutputPath --operator-report
if ($LASTEXITCODE -ne 0) { throw "Capture completed; wiki update failed (exit $LASTEXITCODE). See the execution-failure report above." }
