#Requires -Version 7
<# Tests the real wrapper with a recording Python command; never reads game assets. #>
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$fixture = Join-Path $repoRoot ('.local\handoff-test-' + [guid]::NewGuid().ToString('N'))
$game = Join-Path $fixture 'fake game'
$wiki = Join-Path $fixture 'fake wiki'
New-Item -ItemType Directory -Path $game, $wiki | Out-Null
Set-Content -LiteralPath (Join-Path $game 'Human Host.exe') -Value ''
Set-Content -LiteralPath (Join-Path $wiki 'wiki.py') -Value ''
$global:DecompileHandoffCalls = [System.Collections.Generic.List[object]]::new()
$global:DecompileHandoffFailCall = 0
function py {
    $global:DecompileHandoffCalls.Add(@($args))
    $global:LASTEXITCODE = if ($global:DecompileHandoffCalls.Count -eq $global:DecompileHandoffFailCall) { 7 } else { 0 }
}
function Assert-True([bool]$Value, [string]$Message) {
    if (-not $Value) { throw $Message }
}
function Run-Case([hashtable]$Extra, [int]$ExpectedCalls, [string]$ExpectedError = '') {
    $global:DecompileHandoffCalls.Clear()
    $caught = ''
    try {
        & (Join-Path $PSScriptRoot 'Decompile-GameCode.ps1') -GameDir $game -WikiPath $wiki -OutputPath (Join-Path $fixture 'source output') @Extra
    } catch { $caught = $_.Exception.Message }
    Assert-True ($global:DecompileHandoffCalls.Count -eq $ExpectedCalls) "Expected $ExpectedCalls calls, received $($global:DecompileHandoffCalls.Count). Error: $caught"
    if ($ExpectedError) { Assert-True ($caught -like "*$ExpectedError*") "Unexpected failure: $caught" }
    else { Assert-True (-not $caught) "Unexpected failure: $caught" }
    Assert-True ($global:DecompileHandoffCalls[0][1] -like '*game_catalog\refresh.py') 'Capture must run first.'
    if ($ExpectedCalls -eq 2) {
        $wikiArgs = $global:DecompileHandoffCalls[1]
        Assert-True ($wikiArgs[1] -eq (Join-Path $wiki 'wiki.py')) 'Wrong wiki entrypoint.'
        Assert-True ($wikiArgs[2] -eq 'update') 'Must run the normal update command.'
        Assert-True ($wikiArgs[4] -eq (Join-Path $fixture 'source output')) 'Source path with spaces was not preserved.'
        Assert-True ($wikiArgs[5] -eq '--operator-report') 'Final exception report was not requested.'
    }
}
try {
    Run-Case @{} 2
    Run-Case @{} 2 # unchanged capture also exits zero and follows the same handoff
    Run-Case @{SkipWiki = $true} 1
    Run-Case @{NoGit = $true} 1
    Run-Case @{Assemblies = @('Player')} 1
    $global:DecompileHandoffFailCall = 1
    Run-Case @{} 1 'Game codebase refresh failed'
    $global:DecompileHandoffFailCall = 2
    Run-Case @{} 2 'wiki update failed'
    Write-Host 'Decompile/wiki handoff: 7 cases passed.'
} finally {
    # The fixture has no Git objects or protected files. Bound its exact path.
    $resolved = [System.IO.Path]::GetFullPath($fixture)
    $allowed = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.local')) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture cleanup escaped .local.' }
    Remove-Item -LiteralPath $resolved -Recurse
}
