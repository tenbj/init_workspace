param(
    [string]$ProgramSrcPath,
    [string]$Version,
    [switch]$BumpPatch,
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

function Assert-UnderPath {
    param(
        [string]$Path,
        [string]$Root
    )
    $fullPath = (Normalize-PathString ([System.IO.Path]::GetFullPath($Path))).TrimEnd('\')
    $fullRoot = (Normalize-PathString ([System.IO.Path]::GetFullPath($Root))).TrimEnd('\')
    $prefix = $fullRoot + "\"
    if (-not ($fullPath.Equals($fullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
              $fullPath.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Refusing to modify path outside template root: $Path"
    }
}

function Parse-Version {
    param([string]$Text)
    if ($Text -notmatch '^(\d+)\.(\d+)\.(\d+)$') {
        throw "Invalid version: $Text"
    }
    return [PSCustomObject]@{
        Major = [int]$Matches[1]
        Minor = [int]$Matches[2]
        Patch = [int]$Matches[3]
    }
}

function Bump-PatchVersion {
    param([string]$Text)
    $parsed = Parse-Version $Text
    return "$($parsed.Major).$($parsed.Minor).$($parsed.Patch + 1)"
}

function Get-VersionFromBuildScript {
    param([string]$Path)
    $content = [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
    if ($content -match '(?m)^\$Version\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Cannot read version from build script: $Path"
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

function Write-Utf8NoBomFile {
    param([string]$Path, [string]$Content)
    $parent = Split-Path $Path -Parent
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Write-Utf8BomFile {
    param([string]$Path, [string]$Content)
    $parent = Split-Path $Path -Parent
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($true))
}

function Count-Files {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 0 }
    return @(Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\__pycache__\\' }).Count
}

function Copy-DirectoryFresh {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$TemplateRoot,
        [switch]$DryRun
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Source directory not found: $Source"
    }
    Assert-UnderPath -Path $Destination -Root $TemplateRoot
    if ($DryRun) {
        Write-Host "[WHATIF] Replace directory: $Destination <- $Source"
        return
    }
    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($item in @(Get-ChildItem -LiteralPath $Source -Force)) {
        if ($item.Name -in @("__pycache__", ".git")) { continue }
        Copy-Item -LiteralPath $item.FullName -Destination $Destination -Recurse -Force
    }
    Get-ChildItem -LiteralPath $Destination -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "__pycache__" -or $_.Name -eq ".git" } |
        Remove-Item -Recurse -Force
}

function Copy-FileFresh {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$TemplateRoot,
        [switch]$DryRun
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Source file not found: $Source"
    }
    Assert-UnderPath -Path $Destination -Root $TemplateRoot
    if ($DryRun) {
        Write-Host "[WHATIF] Replace file: $Destination <- $Source"
        return
    }
    New-Item -ItemType Directory -Path (Split-Path $Destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

if ($Version -and $BumpPatch) {
    throw "Use either -Version or -BumpPatch, not both."
}
if ($Version) {
    [void](Parse-Version $Version)
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Find-WorkspaceRoot $scriptDir
$programSrc = if ($ProgramSrcPath) {
    Resolve-InWorkspace -Path $ProgramSrcPath -WorkspaceRoot $workspaceRoot
} else {
    Get-LatestCoreProgramSrc -WorkspaceRoot $workspaceRoot
}

$initPath = Join-Path $programSrc "init_workspace.py"
$buildPath = Join-Path $programSrc "build.ps1"
$templatesRoot = Join-Path $programSrc "templates"
if (-not (Test-Path -LiteralPath $initPath)) { throw "init_workspace.py not found: $initPath" }
if (-not (Test-Path -LiteralPath $buildPath)) { throw "build.ps1 not found: $buildPath" }

$currentVersion = Get-VersionFromBuildScript $buildPath
$targetVersion = if ($Version) { $Version } elseif ($BumpPatch) { Bump-PatchVersion $currentVersion } else { $currentVersion }
$specPath = Join-Path $workspaceRoot ".system\standards\workspace-spec.json"
$specVersion = "-"
if (Test-Path -LiteralPath $specPath) {
    $spec = Get-Content -LiteralPath $specPath -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($spec.version) { $specVersion = [string]$spec.version }
}

$copyPlan = @(
    [PSCustomObject]@{ Kind = "file"; Source = Join-Path $workspaceRoot "AGENTS.md"; Destination = Join-Path $templatesRoot "AGENTS.md" },
    [PSCustomObject]@{ Kind = "file"; Source = Join-Path $workspaceRoot "CLAUDE.md"; Destination = Join-Path $templatesRoot "CLAUDE.md" },
    [PSCustomObject]@{ Kind = "dir"; Source = Join-Path $workspaceRoot ".agents\rules"; Destination = Join-Path $templatesRoot "rules" },
    [PSCustomObject]@{ Kind = "dir"; Source = Join-Path $workspaceRoot ".agents\skills"; Destination = Join-Path $templatesRoot "skills" },
    [PSCustomObject]@{ Kind = "dir"; Source = Join-Path $workspaceRoot ".system\standards"; Destination = Join-Path $templatesRoot "system\standards" }
)

Write-Host "B09 update init program"
Write-Host "  program-src : $(Get-RelativePath -Path $programSrc -Root $workspaceRoot)"
Write-Host "  version     : $currentVersion -> $targetVersion"
Write-Host "  spec        : $specVersion"

foreach ($item in $copyPlan) {
    if ($item.Kind -eq "file") {
        Copy-FileFresh -Source $item.Source -Destination $item.Destination -TemplateRoot $templatesRoot -DryRun:$WhatIf
    } else {
        Copy-DirectoryFresh -Source $item.Source -Destination $item.Destination -TemplateRoot $templatesRoot -DryRun:$WhatIf
    }
}

$claudeJsonPath = Join-Path $templatesRoot ".Claude.json"
$claudeSettingsPath = Join-Path $templatesRoot ".claude\settings.local.json"
if ($WhatIf) {
    Write-Host "[WHATIF] Write safe Claude placeholders"
} else {
    Write-Utf8NoBomFile -Path $claudeJsonPath -Content "{`r`n  `"env`": {},`r`n  `"hasCompletedOnboarding`": true`r`n}`r`n"
    Write-Utf8NoBomFile -Path $claudeSettingsPath -Content "{`r`n  `"permissions`": {`r`n    `"allow`": []`r`n  }`r`n}`r`n"
}

if ($WhatIf) {
    Write-Host "[WHATIF] Update version constants and write update manifest"
    exit 0
}

$initContent = [System.IO.File]::ReadAllText($initPath, [System.Text.UTF8Encoding]::new($false))
$initContent = [regex]::Replace($initContent, '(?m)^SKELETON_VERSION\s*=\s*"[^"]+"', "SKELETON_VERSION = `"$targetVersion`"", 1)
if ($specVersion -ne "-") {
    $initContent = [regex]::Replace($initContent, '(?m)^SSO_SPEC_VERSION\s*=\s*"[^"]+"', "SSO_SPEC_VERSION = `"$specVersion`"", 1)
}
Write-Utf8NoBomFile -Path $initPath -Content $initContent

$buildContent = [System.IO.File]::ReadAllText($buildPath, [System.Text.UTF8Encoding]::new($false))
$buildContent = [regex]::Replace($buildContent, '(?m)^\$Version\s*=\s*"[^"]+"', "`$Version = `"$targetVersion`"", 1)
Write-Utf8BomFile -Path $buildPath -Content $buildContent

$manifestPath = Join-Path $programSrc ".b09_update_manifest.json"
$copied = @()
foreach ($item in $copyPlan) {
    $copied += [ordered]@{
        kind = $item.Kind
        source = (Get-RelativePath -Path $item.Source -Root $workspaceRoot) -replace '\\', '/'
        destination = (Get-RelativePath -Path $item.Destination -Root $workspaceRoot) -replace '\\', '/'
        files = Count-Files $item.Source
    }
}
$manifest = [ordered]@{
    schema = "b09.init_program_update.v1"
    updated_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    program_src = (Get-RelativePath -Path $programSrc -Root $workspaceRoot) -replace '\\', '/'
    version = $targetVersion
    spec_version = $specVersion
    copied = $copied
    notes = "Templates were replaced from current workspace sources without diff comparison."
}
$manifestJson = $manifest | ConvertTo-Json -Depth 8
Write-Utf8NoBomFile -Path $manifestPath -Content ($manifestJson + "`r`n")

Write-Host "[OK] Init program updated."
Write-Host "  manifest : $(Get-RelativePath -Path $manifestPath -Root $workspaceRoot)"
