# Shared helpers for the scripts in tools\. Dot-source it: . "$PSScriptRoot\Common.ps1"

$script:RepoRoot = Split-Path -Parent $PSScriptRoot
$script:HumanHostAppId = 2393970
$script:HumanHostExe = 'Human Host.exe'

function Resolve-HumanHostDir {
    param([string]$GameDir)

    if ($GameDir) {
        if (Test-Path (Join-Path $GameDir $script:HumanHostExe)) { return (Resolve-Path $GameDir).Path }
        throw "Human Host.exe not found in '$GameDir'."
    }

    # 1. GamePaths.local.props override
    $localProps = Join-Path $script:RepoRoot 'GamePaths.local.props'
    if (Test-Path $localProps) {
        $dir = ([xml](Get-Content -Raw $localProps)).Project.PropertyGroup.HumanHostDir | Select-Object -First 1
        if ($dir -and (Test-Path (Join-Path $dir $script:HumanHostExe))) { return $dir }
    }

    # 2. Steam library folders
    $steamRoots = @()
    foreach ($key in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam') {
        $p = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
        if ($p.SteamPath) { $steamRoots += $p.SteamPath }
        if ($p.InstallPath) { $steamRoots += $p.InstallPath }
    }
    $steamRoots += 'C:\Steam', 'C:\Program Files (x86)\Steam'

    $libraries = @()
    foreach ($root in ($steamRoots | Select-Object -Unique)) {
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        $libraries += $root
        if (Test-Path $vdf) {
            $libraries += Select-String -Path $vdf -Pattern '"path"\s+"([^"]+)"' |
                ForEach-Object { $_.Matches[0].Groups[1].Value -replace '\\\\', '\' }
        }
    }
    foreach ($lib in ($libraries | Select-Object -Unique)) {
        $candidate = Join-Path $lib 'steamapps\common\Human Host'
        if (Test-Path (Join-Path $candidate $script:HumanHostExe)) { return $candidate }
    }

    throw 'Human Host install not found. Pass -GameDir or create GamePaths.local.props.'
}

function Test-HumanHostRunning {
    [bool](Get-Process -Name 'Human Host' -ErrorAction SilentlyContinue)
}

function Assert-HumanHostClosed {
    if (Test-HumanHostRunning) {
        throw 'Human Host is running. Close the game first; its loaded DLLs are locked.'
    }
}

function Get-GitHubRelease {
    # Returns the newest non-prerelease release whose tag matches $TagPattern,
    # or the release with exactly $Tag when given.
    param(
        [Parameter(Mandatory)][string]$Repo,
        [string]$Tag,
        [string]$TagPattern = '.*'
    )
    $headers = @{ 'User-Agent' = 'HumanHostMods-tools'; 'Accept' = 'application/vnd.github+json' }
    if ($Tag) {
        return Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$Repo/releases/tags/$Tag"
    }
    # Parentheses enumerate the JSON array; piped directly it arrives as one object.
    (Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/$Repo/releases?per_page=30") |
        Where-Object { -not $_.prerelease -and -not $_.draft -and $_.tag_name -match $TagPattern } |
        Select-Object -First 1
}

function Save-ReleaseAsset {
    # Downloads a release asset into .cache\downloads (reused if already present).
    param([Parameter(Mandatory)]$Release, [Parameter(Mandatory)][string]$AssetName)
    $asset = $Release.assets | Where-Object name -eq $AssetName | Select-Object -First 1
    if (-not $asset) { throw "Release $($Release.tag_name) has no asset named $AssetName." }
    $cache = Join-Path $script:RepoRoot '.cache\downloads'
    New-Item -ItemType Directory -Force $cache | Out-Null
    $target = Join-Path $cache $AssetName
    if (-not (Test-Path $target) -or (Get-Item $target).Length -ne $asset.size) {
        Write-Host "Downloading $AssetName ($([math]::Round($asset.size / 1KB)) KB)"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $target -UseBasicParsing
    }
    $target
}

function Get-InstalledBepInExVersion {
    param([Parameter(Mandatory)][string]$GameDir)
    $dll = Join-Path $GameDir 'BepInEx\core\BepInEx.dll'
    if (-not (Test-Path $dll)) { return $null }
    (Get-Item $dll).VersionInfo.FileVersion
}
