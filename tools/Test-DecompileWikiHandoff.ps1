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
$global:DecompileHandoffTimingSupported = $false
$global:DecompileHandoffThrowHelp = $false
$global:DecompileHandoffReceipt = Join-Path $repoRoot '.local\runs\capture-20261003T000000Z-123-89abcdef01234567.json'
function py {
    $global:DecompileHandoffCalls.Add(@($args))
    $global:LASTEXITCODE = if ($global:DecompileHandoffCalls.Count -eq $global:DecompileHandoffFailCall) { 7 } else { 0 }
    if ($args[-1] -eq '--help') {
        if ($global:DecompileHandoffThrowHelp) { throw 'Native help command failed under strict native error handling.' }
        if ($global:DecompileHandoffTimingSupported) { 'options: --source --operator-report --capture-timing PATH' }
        else { 'options: --source --operator-report' }
    } elseif ($global:DecompileHandoffCalls.Count -eq 1 -and $global:DecompileHandoffReceipt) {
        'Synthetic capture progress before the timing receipt.'
        "CAPTURE_TIMING_RECEIPT=$global:DecompileHandoffReceipt"
    }
}
function Assert-True([bool]$Value, [string]$Message) {
    if (-not $Value) { throw $Message }
}
function Run-Case([hashtable]$Extra, [int]$ExpectedCalls, [string]$ExpectedError = '') {
    $global:DecompileHandoffCalls.Clear()
    $caught = ''
    try {
        & (Join-Path $PSScriptRoot 'Decompile-GameCode.ps1') -GameDir $game -WikiPath $wiki -OutputPath (Join-Path $fixture 'source output') -PythonPackagesPath (Join-Path $fixture 'python packages') @Extra
    } catch { $caught = $_.Exception.Message }
    Assert-True ($global:DecompileHandoffCalls.Count -eq $ExpectedCalls) "Expected $ExpectedCalls calls, received $($global:DecompileHandoffCalls.Count). Error: $caught"
    if ($ExpectedError) { Assert-True ($caught -like "*$ExpectedError*") "Unexpected failure: $caught" }
    else { Assert-True (-not $caught) "Unexpected failure: $caught" }
    for ($index = 0; $index -lt $ExpectedCalls; $index++) {
        $runnerArgs = $global:DecompileHandoffCalls[$index]
        Assert-True ($runnerArgs[0] -eq '-3') 'Runner must use Python 3.'
        $runner = if ($index -eq 0) { 'game_catalog\timing.py' } else { 'game_catalog\processes.py' }
        Assert-True ($runnerArgs[1] -eq (Join-Path $PSScriptRoot $runner)) 'Capture must use the timing runner; wiki commands must use the generic runner.'
        $deadline = if ($index -eq 0) { 14400 } elseif ($index -eq 1) { 120 } else { 15000 }
        Assert-True ($runnerArgs[2] -eq $deadline) "Wrong runner deadline for call $index."
        Assert-True ($runnerArgs[3] -eq 'py') 'Runner must launch the inner Python command.'
    }
    $captureArgs = $global:DecompileHandoffCalls[0][4..($global:DecompileHandoffCalls[0].Count - 1)]
    Assert-True ($captureArgs[0] -eq '-3') 'Capture must use Python 3.'
    Assert-True ($captureArgs[1] -eq (Join-Path $PSScriptRoot 'game_catalog\refresh.py')) 'Capture must run first.'
    Assert-True ($captureArgs[2] -eq '--game' -and $captureArgs[3] -eq $game) 'Wrong capture game path.'
    Assert-True ($captureArgs[4] -eq '--output' -and $captureArgs[5] -eq (Join-Path $fixture 'source output')) 'Capture output path with spaces was not preserved.'
    $expectedCapture = @('-3', (Join-Path $PSScriptRoot 'game_catalog\refresh.py'), '--game', $game,
        '--output', (Join-Path $fixture 'source output'), '--workers', '4', '--python-packages', (Join-Path $fixture 'python packages'))
    if ($Extra.Assemblies) { $expectedCapture += '--assemblies'; $expectedCapture += $Extra.Assemblies }
    if ($Extra.NoGit) { $expectedCapture += '--no-git' }
    Assert-True (($captureArgs -join '|') -eq ($expectedCapture -join '|')) 'Capture arguments must not choose receipt or checkpoint paths.'
    $receiptPath = $global:DecompileHandoffReceipt
    if ($ExpectedCalls -eq 3) {
        $helpArgs = $global:DecompileHandoffCalls[1][4..($global:DecompileHandoffCalls[1].Count - 1)]
        Assert-True (($helpArgs -join '|') -eq (@('-3', (Join-Path $wiki 'wiki.py'), 'update', '--help') -join '|')) 'Wrong wiki capability probe.'
        $wikiArgs = $global:DecompileHandoffCalls[2][4..($global:DecompileHandoffCalls[2].Count - 1)]
        $supportsTiming = $global:DecompileHandoffTimingSupported -and $global:DecompileHandoffFailCall -ne 2 -and -not $global:DecompileHandoffThrowHelp -and $receiptPath
        $argumentCount = if ($supportsTiming) { 8 } else { 6 }
        Assert-True ($wikiArgs.Count -eq $argumentCount -and $wikiArgs[0] -eq '-3') 'Wrong inner wiki command shape.'
        Assert-True ($wikiArgs[1] -eq (Join-Path $wiki 'wiki.py')) 'Wrong wiki entrypoint.'
        Assert-True ($wikiArgs[2] -eq 'update') 'Must run the normal update command.'
        Assert-True ($wikiArgs[3] -eq '--source') 'Source option was not supplied.'
        Assert-True ($wikiArgs[4] -eq (Join-Path $fixture 'source output')) 'Source path with spaces was not preserved.'
        Assert-True ($wikiArgs[5] -eq '--operator-report') 'Final exception report was not requested.'
        if ($supportsTiming) {
            Assert-True ($wikiArgs[6] -eq '--capture-timing' -and $wikiArgs[7] -eq $receiptPath) 'Capture receipt was not appended after the operator report.'
        }
    }
}
try {
    Run-Case @{} 3
    $global:DecompileHandoffTimingSupported = $true
    Run-Case @{} 3
    Run-Case @{} 3 # unchanged capture also exits zero and follows the same handoff
    $savedReceipt = $global:DecompileHandoffReceipt
    $global:DecompileHandoffReceipt = $null
    Run-Case @{} 3 # unavailable diagnostics must not prevent the wiki handoff
    $global:DecompileHandoffReceipt = $savedReceipt
    Run-Case @{SkipWiki = $true} 1
    Run-Case @{NoGit = $true} 1
    Run-Case @{Assemblies = @('Player')} 1
    $global:DecompileHandoffFailCall = 1
    Run-Case @{} 1 'Game codebase refresh failed'
    $global:DecompileHandoffFailCall = 2
    Run-Case @{} 3 # failed help probe omits the new option
    $global:DecompileHandoffFailCall = 0
    $global:DecompileHandoffThrowHelp = $true
    $PSNativeCommandUseErrorActionPreference = $true
    Run-Case @{} 3 # a throwing native help probe must also omit the option
    $global:DecompileHandoffThrowHelp = $false
    $global:DecompileHandoffFailCall = 3
    Run-Case @{} 3 'wiki update failed'
    $global:DecompileHandoffFailCall = 1
    Run-Case @{SkipWiki = $true} 1 'Game codebase refresh failed (exit 7).'
    Write-Host 'Decompile/wiki handoff: 12 cases passed.'
} finally {
    # The fixture has no Git objects or protected files. Bound its exact path.
    $resolved = [System.IO.Path]::GetFullPath($fixture)
    $allowed = [System.IO.Path]::GetFullPath((Join-Path $repoRoot '.local')) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($allowed, [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture cleanup escaped .local.' }
    Remove-Item -LiteralPath $resolved -Recurse
}
