#Requires -Version 7
<# Binary stdout only. The game's decoder runs in a separate process and never writes a decoded file. #>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$GameData, [Parameter(Mandatory)][string]$BundlePath)
$ErrorActionPreference = 'Stop'
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $GameData 'Managed/UIResource.dll'))
$method = $assembly.GetType('LootIndicator.Init.LootIndiC', $true).GetMethod('DeLootIndiBytes')
$decoded = $method.Invoke($null, [object[]]@(,[IO.File]::ReadAllBytes($BundlePath)))
if ([Text.Encoding]::ASCII.GetString($decoded, 0, 7) -ne 'UnityFS') {
    throw "The installed game decoder did not produce UnityFS data for $BundlePath"
}
$stdout = [Console]::OpenStandardOutput()
$stdout.Write($decoded, 0, $decoded.Length)
$stdout.Flush()
