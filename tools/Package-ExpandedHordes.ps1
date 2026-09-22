#Requires -Version 7.0
[CmdletBinding()]
param([string]$GameDir)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/Common.ps1"
$GameDir = Resolve-HumanHostDir -GameDir $GameDir
$project = Join-Path $script:RepoRoot 'mods/ExpandedHordes/ExpandedHordes.csproj'
$version = [string]([xml](Get-Content -LiteralPath $project -Raw)).Project.PropertyGroup.Version
$sourceDir = Join-Path $script:RepoRoot 'release/ExpandedHordes'
$outputDir = Join-Path $script:RepoRoot "dist/ExpandedHordes-$version"
$contentDir = Join-Path $outputDir 'content'
$payloadDir = Join-Path $contentDir 'ExpandedHordes'
$allowed = @('ExpandedHordes/ExpandedHordes.dll', 'ExpandedHordes/README.txt')

# Never recursively copy an installation or erase unknown files from prior work.
if (Test-Path -LiteralPath $contentDir) {
    foreach ($file in Get-ChildItem -LiteralPath $contentDir -Recurse -File) {
        $relative = [System.IO.Path]::GetRelativePath($contentDir, $file.FullName).Replace('\', '/')
        if ($relative -notin $allowed) { throw "Unexpected payload file: $relative. Review it before packaging." }
    }
}

dotnet build (Join-Path $script:RepoRoot 'HumanHostMods.slnx') -c Release "-p:HumanHostDir=$GameDir"
if ($LASTEXITCODE -ne 0) { throw 'Solution build failed.' }
dotnet run --project (Join-Path $script:RepoRoot 'tests/ExpandedHordes.Checks') -c Release -- (Join-Path $GameDir 'Human Host_Data/Managed')
if ($LASTEXITCODE -ne 0) { throw 'Policy / installed-assembly checks failed.' }

$dll = Join-Path $script:RepoRoot 'mods/ExpandedHordes/bin/Release/ExpandedHordes.dll'
if ([System.Diagnostics.FileVersionInfo]::GetVersionInfo($dll).ProductVersion.Split('+')[0] -ne $version) {
    throw 'Assembly and package versions disagree.'
}
$copiedDlls = @(Get-ChildItem -LiteralPath (Split-Path $dll) -Filter '*.dll' -File)
if ($copiedDlls.Count -ne 1 -or $copiedDlls[0].Name -ne 'ExpandedHordes.dll') {
    throw 'Unexpected DLLs in build output; game/dependency assemblies must never be shipped.'
}
New-Item -ItemType Directory -Path $payloadDir -Force | Out-Null
Copy-Item -LiteralPath $dll -Destination (Join-Path $payloadDir 'ExpandedHordes.dll') -Force
Copy-Item -LiteralPath (Join-Path $sourceDir 'README.txt') -Destination $payloadDir -Force
foreach ($name in @('workshop-description.txt', 'PUBLISHING.md', 'PLAYTEST.md')) {
    Copy-Item -LiteralPath (Join-Path $sourceDir $name) -Destination $outputDir -Force
}

# A fresh sample never inherits release-directory or live user settings.
$sample = Join-Path $outputDir 'sample.cfg'
if (Test-Path -LiteralPath $sample) { Remove-Item -LiteralPath $sample }
dotnet run --project (Join-Path $PSScriptRoot 'ExpandedHordes.Config') -c Release "-p:HumanHostDir=$GameDir" -- $sample
if ($LASTEXITCODE -ne 0) { throw 'Sample config generation failed.' }
if (!(Get-Content -LiteralPath $sample -Raw).StartsWith("## Settings file was created by plugin Expanded Hordes v$version")) {
    throw 'Plugin identity and package versions disagree.'
}
pwsh -NoProfile -File (Join-Path $sourceDir 'New-Preview.ps1') -Path (Join-Path $outputDir 'preview.png')
if ($LASTEXITCODE -ne 0) { throw 'Preview generation failed.' }

# Keep Steam's identity after an upload. Packaging never uploads or calls SteamCMD.
$vdfPath = Join-Path $outputDir 'workshop.vdf'
$publishedId = '0'
if (Test-Path -LiteralPath $vdfPath) {
    $match = [regex]::Match((Get-Content -LiteralPath $vdfPath -Raw), '"publishedfileid"\s+"([0-9]+)"')
    if (!$match.Success) { throw 'Existing workshop.vdf has no valid publishedfileid; refusing to replace it.' }
    $publishedId = $match.Groups[1].Value
}
function VdfText([string]$value) {
    return $value.Replace('\', '\\').Replace('"', '\"').Replace("`r", '').Replace("`n", '\n')
}
$description = VdfText (Get-Content -LiteralPath (Join-Path $sourceDir 'workshop-description.txt') -Raw)
$contentPath = VdfText $contentDir.Replace('\', '/')
$previewPath = VdfText (Join-Path $outputDir 'preview.png').Replace('\', '/')
$vdf = @"
"workshopitem"
{
    "appid" "2393970"
    "publishedfileid" "$publishedId"
    "contentfolder" "$contentPath"
    "previewfile" "$previewPath"
    "visibility" "2"
    "title" "Expanded Hordes"
    "description" "$description"
    "changenote" "$version - horde resistance, corpse retention and optional diagnostics."
}
"@
[System.IO.File]::WriteAllText($vdfPath, $vdf + "`n")

# ZIP entry order/timestamps are fixed so a repeated build is byte-identical.
$zipPath = Join-Path $outputDir "ExpandedHordes-$version.zip"
$stream = [System.IO.File]::Open($zipPath, 'Create', 'ReadWrite', 'None')
$archive = [System.IO.Compression.ZipArchive]::new($stream, 'Create', $false)
try {
    foreach ($relative in $allowed) {
        $entry = $archive.CreateEntry($relative, 'Optimal')
        $entry.LastWriteTime = [DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
        $entryStream = $entry.Open()
        $inputStream = [System.IO.File]::OpenRead((Join-Path $contentDir $relative))
        try { $inputStream.CopyTo($entryStream) }
        finally { $inputStream.Dispose(); $entryStream.Dispose() }
    }
}
finally { $archive.Dispose(); $stream.Dispose() }

$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    if ($archive.Entries.Count -ne $allowed.Count) { throw 'ZIP contains an unexpected number of files.' }
    foreach ($entry in $archive.Entries) {
        if ($entry.FullName -notin $allowed) { throw "Unexpected ZIP file: $($entry.FullName)" }
        $entryStream = $entry.Open()
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { $zipHash = [Convert]::ToHexString($sha.ComputeHash($entryStream)) }
        finally { $sha.Dispose(); $entryStream.Dispose() }
        if ($zipHash -ne (Get-FileHash -LiteralPath (Join-Path $contentDir $entry.FullName)).Hash) {
            throw "ZIP content mismatch: $($entry.FullName)"
        }
    }
}
finally { $archive.Dispose() }

$steamManifest = Join-Path (Split-Path (Split-Path $GameDir -Parent) -Parent) 'appmanifest_2393970.acf'
$gameBuild = 'unknown'
if (Test-Path -LiteralPath $steamManifest) {
    $match = [regex]::Match((Get-Content -LiteralPath $steamManifest -Raw), '"buildid"\s+"([0-9]+)"')
    if ($match.Success) { $gameBuild = $match.Groups[1].Value }
}
$info = [ordered]@{
    mod = 'Expanded Hordes'; version = $version; steamAppId = 2393970; gameBuild = $gameBuild
    runtimePlaytest = 'pending'; publication = 'not performed by this script'
    dllSha256 = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant()
    gameAssemblySha256 = [ordered]@{}
}
foreach ($name in @('Terrain.dll', 'Creature.dll', 'AI.dll')) {
    $info.gameAssemblySha256[$name] = (Get-FileHash -LiteralPath (Join-Path $GameDir "Human Host_Data/Managed/$name") -Algorithm SHA256).Hash.ToLowerInvariant()
}
[System.IO.File]::WriteAllText((Join-Path $outputDir 'build-info.json'), ($info | ConvertTo-Json -Depth 4) + "`n")
$packageFiles = @('content/ExpandedHordes/ExpandedHordes.dll', 'content/ExpandedHordes/README.txt',
    'workshop-description.txt', 'PUBLISHING.md', 'PLAYTEST.md', 'sample.cfg', 'preview.png',
    'workshop.vdf', 'build-info.json', "ExpandedHordes-$version.zip")
$hashes = foreach ($relative in $packageFiles) {
    $hash = (Get-FileHash -LiteralPath (Join-Path $outputDir $relative) -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
}
[System.IO.File]::WriteAllLines((Join-Path $outputDir 'SHA256SUMS.txt'), $hashes)
Write-Output "Prepared release $version at $outputDir. Runtime play test and publication remain pending."
