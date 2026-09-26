#Requires -Version 7
<#
.SYNOPSIS
    Refreshes the local, text-only game source and serialized data catalog.
.DESCRIPTION
    Decompiles all non-framework managed assemblies, inventories installed inputs,
    exports serialized gameplay metadata, resolves references across bundles, and
    generates readable loot/item views. Media payloads are never exported.
    Stages and validates output before replacing the previous local Git snapshot.
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
    [string]$PythonPackagesPath
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
