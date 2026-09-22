#Requires -Version 7.0
[CmdletBinding()]
param([string]$GameDir)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/Common.ps1"
$GameDir = Resolve-HumanHostDir -GameDir $GameDir
Assert-HumanHostClosed

$project = Join-Path $script:RepoRoot 'mods/ExpandedHordes/ExpandedHordes.csproj'
dotnet build $project -c Release "-p:HumanHostDir=$GameDir"
if ($LASTEXITCODE -ne 0) { throw 'Expanded Hordes build failed.' }

Assert-HumanHostClosed
$config = Join-Path $GameDir 'BepInEx/config/rkgamemods.humanhost.expandedhordes.cfg'
dotnet run --project (Join-Path $PSScriptRoot 'ExpandedHordes.Config') -c Release "-p:HumanHostDir=$GameDir" -- $config
if ($LASTEXITCODE -ne 0) { throw 'Expanded Hordes config initialization failed.' }

Assert-HumanHostClosed
$source = Join-Path $script:RepoRoot 'mods/ExpandedHordes/bin/Release/ExpandedHordes.dll'
$destinationDir = Join-Path $GameDir 'BepInEx/plugins/ExpandedHordes'
New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
$destination = Join-Path $destinationDir 'ExpandedHordes.dll'
Copy-Item -LiteralPath $source -Destination $destination -Force
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    throw 'Installed DLL did not match the build.'
}
Write-Output "Installed and hash-verified: $destination"
Write-Output "HHMM config: $config"
