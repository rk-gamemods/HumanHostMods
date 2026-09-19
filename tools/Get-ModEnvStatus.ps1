<#
.SYNOPSIS
    Reports the state of the Human Host modding environment.

.DESCRIPTION
    Read-only. Checks the game install, Steam build ID, BepInEx and Doorstop files,
    the BepInEx folders a first launch creates, the last BepInEx log, installed
    plugins, and the local .NET SDK and ilspycmd.
    Exits with code 1 if a required piece is missing.
#>
[CmdletBinding()]
param([string]$GameDir)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\Common.ps1"

$failures = 0
function Report([string]$Name, [bool]$Ok, [string]$Detail) {
    $mark = if ($Ok) { 'ok  ' } else { 'FAIL' }
    Write-Host ("[{0}] {1,-26} {2}" -f $mark, $Name, $Detail)
    if (-not $Ok) { $script:failures++ }
}

$GameDir = Resolve-HumanHostDir -GameDir $GameDir
Report 'Game folder' $true $GameDir

$manifest = Get-ChildItem -Path (Join-Path $GameDir '..\..') -Filter "appmanifest_$($script:HumanHostAppId).acf" -ErrorAction SilentlyContinue
if ($manifest) {
    $build = (Select-String -Path $manifest.FullName -Pattern '"buildid"\s+"(\d+)"').Matches[0].Groups[1].Value
    Report 'Steam build ID' $true $build
}
Report 'Game running' $true ([string](Test-HumanHostRunning))

foreach ($f in 'winhttp.dll', 'doorstop_config.ini', '.doorstop_version') {
    $p = Join-Path $GameDir $f
    $detail = if ($f -eq '.doorstop_version' -and (Test-Path $p)) { "Doorstop $((Get-Content $p -Raw).Trim())" } else { '' }
    Report $f (Test-Path $p) $detail
}

$bepVersion = Get-InstalledBepInExVersion -GameDir $GameDir
Report 'BepInEx core' ([bool]$bepVersion) $bepVersion

foreach ($d in 'plugins', 'config', 'patchers') {
    Report "BepInEx\$d" (Test-Path (Join-Path $GameDir "BepInEx\$d")) ''
}
Report 'BepInEx.cfg' (Test-Path (Join-Path $GameDir 'BepInEx\config\BepInEx.cfg')) '(created on first launch)'

$log = Join-Path $GameDir 'BepInEx\LogOutput.log'
if (Test-Path $log) {
    $lines = Get-Content $log
    $header = $lines | Select-Object -First 1
    $unity = ($lines | Select-String 'Running under Unity' | Select-Object -First 1).Line
    $chain = [bool]($lines | Select-String 'Chainloader startup complete')
    $logVersion = if ($header -match 'BepInEx ([\d.]+)') { $Matches[1] } else { '' }
    Report 'Last log' $true "$((Get-Item $log).LastWriteTime) | $header"
    Report 'Log version matches core' ($logVersion -eq $bepVersion) "log $logVersion, core $bepVersion"
    Report 'Chainloader completed' $chain ''
    if ($unity) { Report 'Unity' $true ($unity -replace '.*Running under Unity ', '') }
    $errors = @($lines | Select-String '^\[(Error|Fatal)')
    Report 'Log errors' $true "$($errors.Count) error/fatal lines"
} else {
    Report 'Last log' $false 'No LogOutput.log. Launch the game once.'
}

$plugins = Join-Path $GameDir 'BepInEx\plugins'
if (Test-Path $plugins) {
    Write-Host ''
    Write-Host 'Plugins:'
    Get-ChildItem $plugins -Recurse -Filter *.dll | ForEach-Object {
        $v = $_.VersionInfo.FileVersion
        Write-Host ("  {0,-60} {1}" -f $_.FullName.Substring($plugins.Length + 1), $v)
    }
}

Write-Host ''
$sdks = & dotnet --list-sdks 2>$null
Report '.NET SDK' ([bool]$sdks) (($sdks | ForEach-Object { ($_ -split ' ')[0] }) -join ', ')
$ilspy = & ilspycmd --version 2>$null | Select-Object -First 1
Report 'ilspycmd' ([bool]$ilspy) $ilspy

if ($failures) { Write-Host "`n$failures check(s) failed."; exit 1 }
Write-Host "`nAll checks passed."
