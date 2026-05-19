param(
    [string]$ProgramSrcPath,
    [string]$ExpectedVersion,
    [switch]$SkipUpdateCheck,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
chcp 65001 > $null

function Normalize-PathString {
    param([string]$Path)
    return ($Path -replace '/', '\')
}

function Find-WorkspaceRoot {
    param([string]$StartPath)
    $searchDir = [System.IO.Path]::GetFullPath($StartPath)
    while ($searchDir) {
        if ((Test-Path -LiteralPath (Join-Path $searchDir ".history")) -and
            (Test-Path -LiteralPath (Join-Path $searchDir ".agents"))) {
            return $searchDir
        }
        $parent = Split-Path $searchDir -Parent
        if ($parent -eq $searchDir) { break }
        $searchDir = $parent
    }
    throw "Workspace root not found."
}

function Get-RelativePath {
    param(
        [string]$Path,
        [string]$Root
    )
    $fullPath = (Normalize-PathString ([System.IO.Path]::GetFullPath($Path))).TrimEnd('\')
    $fullRoot = (Normalize-PathString ([System.IO.Path]::GetFullPath($Root))).TrimEnd('\')
    if ($fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) { return "" }
    $prefix = $fullRoot + "\"
    if (-not $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path escapes workspace root: $Path"
    }
    return $fullPath.Substring($prefix.Length)
}

function Resolve-InWorkspace {
    param(
        [string]$Path,
        [string]$WorkspaceRoot
    )
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $resolved = [System.IO.Path]::GetFullPath($Path)
    } else {
        $resolved = [System.IO.Path]::GetFullPath((Join-Path $WorkspaceRoot $Path))
    }
    [void](Get-RelativePath -Path $resolved -Root $WorkspaceRoot)
    return $resolved
}

function Get-LatestCoreProgramSrc {
    param([string]$WorkspaceRoot)
    $outputRoot = Join-Path $WorkspaceRoot "output"
    if (-not (Test-Path -LiteralPath $outputRoot)) {
        throw "output directory not found."
    }

    $stableSrc = Join-Path (Join-Path (Join-Path $outputRoot "00_系统治理") "03_代码程序") "src"
    if ((Test-Path -LiteralPath (Join-Path $stableSrc "init_workspace.py")) -and
        (Test-Path -LiteralPath (Join-Path $stableSrc "build.ps1"))) {
        return $stableSrc
    }

    $candidates = @()
    foreach ($coreDir in @(Get-ChildItem -LiteralPath $outputRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^00_.+_v(\d+\.\d+\.\d+)$' })) {
        $coreVersion = [version]$Matches[1]
        foreach ($programDir in @(Get-ChildItem -LiteralPath $coreDir.FullName -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^03_.+_v(\d+\.\d+\.\d+)$' })) {
            $programVersion = [version]$Matches[1]
            $src = Join-Path $programDir.FullName "src"
            if ((Test-Path -LiteralPath (Join-Path $src "init_workspace.py")) -and
                (Test-Path -LiteralPath (Join-Path $src "build.ps1"))) {
                $candidates += [PSCustomObject]@{
                    CoreVersion = $coreVersion
                    ProgramVersion = $programVersion
                    Path = $src
                }
            }
        }
    }

    if ($candidates.Count -eq 0) {
        throw "No core init program src found under output/00_系统治理/03_代码程序/src or legacy versioned paths."
    }
    return @($candidates | Sort-Object CoreVersion, ProgramVersion -Descending)[0].Path
}

function Get-VersionFromBuildScript {
    param([string]$Path)
    $content = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
    if ($content -match '(?m)^\$Version\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Cannot read version from build script: $Path"
}

function Write-Utf8NoBomFile {
    param([string]$Path, [string]$Content)
    $parent = Split-Path $Path -Parent
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

if ($ExpectedVersion -and $ExpectedVersion -notmatch '^\d+\.\d+\.\d+$') {
    throw "Invalid ExpectedVersion: $ExpectedVersion"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Find-WorkspaceRoot $scriptDir
$programSrc = if ($ProgramSrcPath) {
    Resolve-InWorkspace -Path $ProgramSrcPath -WorkspaceRoot $workspaceRoot
} else {
    Get-LatestCoreProgramSrc -WorkspaceRoot $workspaceRoot
}

$buildScript = Join-Path $programSrc "build.ps1"
$manifestPath = Join-Path $programSrc ".b09_update_manifest.json"
if (-not (Test-Path -LiteralPath $buildScript)) { throw "build.ps1 not found: $buildScript" }

$currentVersion = Get-VersionFromBuildScript $buildScript
if ($ExpectedVersion -and $currentVersion -ne $ExpectedVersion) {
    throw "Build script version is $currentVersion, expected $ExpectedVersion."
}

$manifest = $null
if (-not $SkipUpdateCheck) {
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Update manifest is missing. Run scripts/update_init_program.ps1 successfully before building."
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($manifest.version -and $manifest.version -ne $currentVersion) {
        throw "Update manifest version $($manifest.version) does not match build script version $currentVersion."
    }
}

Write-Host "B09 build init exe"
Write-Host "  program-src : $(Get-RelativePath -Path $programSrc -Root $workspaceRoot)"
Write-Host "  version     : $currentVersion"
Write-Host "  update-check: $(-not $SkipUpdateCheck)"

if ($WhatIf) {
    Write-Host "[WHATIF] Would run build.ps1 and calculate SHA256."
    exit 0
}

Push-Location $programSrc
try {
    & powershell -ExecutionPolicy Bypass -File $buildScript
    if ($LASTEXITCODE -ne 0) {
        throw "build.ps1 failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}

$distDir = Join-Path (Split-Path $programSrc -Parent) "dist"
if (-not (Test-Path -LiteralPath $distDir)) {
    throw "dist directory not found after build: $distDir"
}
$exe = @(Get-ChildItem -LiteralPath $distDir -Filter "*.exe" -File | Sort-Object LastWriteTime -Descending)[0]
if (-not $exe) {
    throw "No exe found after build."
}
$hash = Get-FileHash -LiteralPath $exe.FullName -Algorithm SHA256
$sizeBytes = (Get-Item -LiteralPath $exe.FullName).Length
$sizeMB = [math]::Round($sizeBytes / 1MB, 2)

$buildManifestPath = Join-Path $distDir ".b09_build_manifest.json"
$buildManifest = [ordered]@{
    schema = "b09.init_exe_build.v1"
    built_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    program_src = (Get-RelativePath -Path $programSrc -Root $workspaceRoot) -replace '\\', '/'
    version = $currentVersion
    asset = (Get-RelativePath -Path $exe.FullName -Root $workspaceRoot) -replace '\\', '/'
    size_bytes = $sizeBytes
    size_mb = $sizeMB
    sha256 = $hash.Hash
    update_manifest = if ($manifest) { (Get-RelativePath -Path $manifestPath -Root $workspaceRoot) -replace '\\', '/' } else { $null }
}
Write-Utf8NoBomFile -Path $buildManifestPath -Content (($buildManifest | ConvertTo-Json -Depth 6) + "`r`n")

Write-Host "[OK] EXE built."
Write-Host "  asset  : $(Get-RelativePath -Path $exe.FullName -Root $workspaceRoot)"
Write-Host "  size   : $sizeMB MB"
Write-Host "  sha256 : $($hash.Hash)"
Write-Host "  manifest : $(Get-RelativePath -Path $buildManifestPath -Root $workspaceRoot)"
