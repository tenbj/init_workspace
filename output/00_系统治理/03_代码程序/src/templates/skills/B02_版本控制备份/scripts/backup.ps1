<#
.SYNOPSIS
    File, folder, config, memory, and project backup script.
.DESCRIPTION
    Supports five modes:
    - PROJECT : output/ subproject folders — snapshot entire folder to .history with version + timestamp, bump 版本记录.md only
    - FOLDER  : .agents/skills/ folders or .system/ subfolders — snapshot with timestamp, source unchanged; .system snapshots append .history/.system/更新日志.md
    - CONFIG  : .agents/rules/ files and root independent files — copy with timestamp, source unchanged
    - MEMORY  : versioned .memory files — stable live filename, old versions → .history/.memory/
    - FILE    : legacy single-file mode (not used for output/ paths)

    output/ backup design (PROJECT mode):
    - Subproject folder named: {编号}_{主题}
    - Backup: Copy entire folder → .history/output/{name}_v{x.y.z}_{timestamp}
    - Keep live folder stable; do not rename output/ or .memory/对话记录 files
    - 版本记录.md inside each subproject tracks version history
    - Subproject version and individual file versions are independent
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath,

    [Parameter(Mandatory = $false)]
    [ValidateSet("MAJOR", "MINOR", "PATCH")]
    [string]$ChangeType = "PATCH",

    [Parameter(Mandatory = $false)]
    [ValidateSet("PROJECT", "FOLDER", "CONFIG", "MEMORY", "FILE", "AUTO")]
    [string]$Mode = "AUTO"
)

chcp 65001 > $null

function Normalize-PathString {
    param([string]$Path)
    return ($Path -replace '/', '\')
}

function Get-RelativePath {
    param(
        [string]$Path,
        [string]$Root
    )

    $normalizedPath = (Normalize-PathString ([System.IO.Path]::GetFullPath($Path))).TrimEnd('\')
    $normalizedRoot = (Normalize-PathString ([System.IO.Path]::GetFullPath($Root))).TrimEnd('\')
    if ($normalizedPath.Equals($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) { return "" }

    $rootPrefix = $normalizedRoot + "\"
    if (-not $normalizedPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Error "Target must stay inside workspace root: $Path"
        exit 1
    }
    return $normalizedPath.Substring($rootPrefix.Length)
}

function Find-WorkspaceRoot {
    param([string]$StartPath)
    if (-not $StartPath) { return $null }
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
    return $null
}

function Resolve-ProjectPath {
    param(
        [string]$Path,
        [string]$WorkspaceRoot
    )

    $rootFull = [System.IO.Path]::GetFullPath($WorkspaceRoot)
    if ([System.IO.Path]::IsPathRooted($Path)) {
        $fullPath = [System.IO.Path]::GetFullPath($Path)
    } else {
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path $rootFull $Path))
    }

    $normalizedRoot = (Normalize-PathString $rootFull).TrimEnd('\')
    $normalizedFull = (Normalize-PathString $fullPath).TrimEnd('\')
    $rootPrefix = $normalizedRoot + "\"
    if (-not ($normalizedFull.Equals($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
              $normalizedFull.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase))) {
        Write-Error "Target escapes workspace root: $Path"
        exit 1
    }
    return $fullPath
}

function Parse-Version {
    param([string]$Version)
    if ($Version -match '^(\d+)\.(\d+)\.(\d+)$') {
        return @{
            Major = [int]$Matches[1]
            Minor = [int]$Matches[2]
            Patch = [int]$Matches[3]
        }
    }
    return $null
}

function Get-VersionFromName {
    param([string]$BaseName)
    if ($BaseName -match '_v(\d+\.\d+\.\d+)$') { return $Matches[1] }
    if ($BaseName -match '_v(\d+\.\d+)$') { return "$($Matches[1]).0" }
    return $null
}

function Get-PureName {
    param([string]$BaseName)
    if ($BaseName -match '^(.+)_v\d+\.\d+(\.\d+)?$') { return $Matches[1] }
    return $BaseName
}

function Bump-Version {
    param([string]$CurrentVersion, [string]$Type)
    $parsed = Parse-Version $CurrentVersion
    if (-not $parsed) {
        Write-Error "Cannot parse version: $CurrentVersion"
        exit 1
    }

    switch ($Type) {
        "MAJOR" { return "$($parsed.Major + 1).0.0" }
        "MINOR" { return "$($parsed.Major).$($parsed.Minor + 1).0" }
        "PATCH" { return "$($parsed.Major).$($parsed.Minor).$($parsed.Patch + 1)" }
    }
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-MemoryVersionFromContent {
    param([string]$Path)
    $firstLine = Get-Content -Path $Path -Encoding UTF8 -TotalCount 1 -ErrorAction SilentlyContinue
    if ($firstLine -match '<!--\s*memory-version:\s*(\d+\.\d+\.\d+)\s*-->') {
        return $Matches[1]
    }
    return $null
}

function Get-MemoryKind {
    param(
        [string]$Path,
        [string]$WorkspaceRoot
    )

    $relativePath = Get-RelativePath -Path $Path -Root $WorkspaceRoot
    $parts = $relativePath -split '\\'
    if ($parts.Count -eq 0 -or $parts[0] -ne '.memory') {
        return $null
    }

    if ((Get-Item $Path).PSIsContainer) {
        return "MEMORY_FOLDER"
    }

    $fileName = $parts[-1]
    $versionFromHeader = Get-MemoryVersionFromContent $Path

    if ($fileName -match '_v\d+\.\d+(\.\d+)?\.[^.]+$') {
        return "VERSIONED_COPY"
    }
    if ($parts.Count -eq 2) {
        return "VERSIONED_ROOT"
    }
    if ($fileName -eq "rules-skills.md") {
        return "APPEND_ONLY"
    }
    if ($versionFromHeader) {
        return "VERSIONED"
    }
    if ($fileName -match '_v\d+\.\d+\.\d+\.[^.]+$') {
        return "VERSIONED"
    }
    if ($fileName -match '_20\d{10}\.md$') {
        return "APPEND_ONLY"
    }

    return "APPEND_ONLY"
}

function Set-MemoryVersionHeader {
    param(
        [string]$Path,
        [string]$NewVersion
    )

    $content = Get-Content -Path $Path -Raw -Encoding UTF8
    $header = "<!-- memory-version: $NewVersion -->"

    if ($content -match '^\s*<!--\s*memory-version:\s*\d+\.\d+\.\d+\s*-->') {
        $updated = [regex]::Replace(
            $content,
            '^\s*<!--\s*memory-version:\s*\d+\.\d+\.\d+\s*-->',
            $header,
            1
        )
    } else {
        $updated = $header + "`r`n" + $content
    }

    [System.IO.File]::WriteAllText($Path, $updated, [System.Text.UTF8Encoding]::new($false))
}

function Get-ProjectFullName {
    param([string]$FolderName)
    if ($FolderName -match '^(\d+_.+)_v\d+\.\d+\.\d+$') {
        return $Matches[1]
    }
    if ($FolderName -match '^\d+_.+$') {
        return $FolderName
    }
    return $null
}

function Get-ProjectTopic {
    param([string]$FolderName)
    $fullName = Get-ProjectFullName $FolderName
    if (-not $fullName) { return $null }
    $parts = $fullName -split '_', 2
    if ($parts.Count -ge 2) {
        return $parts[1]
    }
    return $fullName
}

function Get-LatestProjectVersionFromRecord {
    param([string]$VersionRecordPath)

    if (-not (Test-Path -LiteralPath $VersionRecordPath)) {
        return $null
    }

    try {
        $content = Get-Content -LiteralPath $VersionRecordPath -Encoding UTF8 -Raw
        $versions = @([regex]::Matches($content, '(?m)^##\s+v(\d+\.\d+\.\d+)\b') |
            ForEach-Object { [version]$_.Groups[1].Value })
        if ($versions.Count -gt 0) {
            return ([string](@($versions | Sort-Object -Descending)[0]))
        }
    } catch {}

    return $null
}

function Update-VersionRecord {
    param(
        [string]$VersionRecordPath,
        [string]$NewVersion,
        [string]$ChangeType,
        [string]$DisplayTimestamp,
        [string]$ProjectTopic
    )

    $entry = @"

## v$NewVersion ($DisplayTimestamp)

**变更类型**：$ChangeType
**变更描述**：（待填写）

**子文件变更明细**：

| 文件 | 版本变更 | 变更描述 |
|------|---------|---------|
| （待填写） | | |

---

"@

    if (Test-Path $VersionRecordPath) {
        $content = [System.IO.File]::ReadAllText($VersionRecordPath, [System.Text.UTF8Encoding]::new($false))
        if ($content -match '^(#[^\n]*\n\n>[^\n]*\n\n---)') {
            $updated = $Matches[1] + $entry + ($content.Substring($Matches[1].Length))
            [System.IO.File]::WriteAllText($VersionRecordPath, $updated, [System.Text.UTF8Encoding]::new($false))
        } else {
            $updated = $entry + $content
            [System.IO.File]::WriteAllText($VersionRecordPath, $updated, [System.Text.UTF8Encoding]::new($false))
        }
    } else {
        $title = @"
# 版本记录 · $ProjectTopic

> 记录子项目的版本变更历史。

---

"@
        [System.IO.File]::WriteAllText($VersionRecordPath, ($title + $entry), [System.Text.UTF8Encoding]::new($false))
    }
}

function Get-DeclaredVersionFromFile {
    param([string]$Path)

    $fileName = Split-Path $Path -Leaf

    if ($fileName -eq "workspace-spec.json") {
        try {
            $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($json.version) { return "v$($json.version)" }
        } catch {}
    }

    try {
        $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8 -TotalCount 30 -ErrorAction Stop)
        foreach ($line in $lines) {
            if ($line -match '版本[：:]\s*([vV]?\d+\.\d+\.\d+)') {
                $version = $Matches[1]
                if ($version -notmatch '^[vV]') { $version = "v$version" }
                return $version
            }
            if ($line -match 'memory-version:\s*(\d+\.\d+\.\d+)') {
                return "v$($Matches[1])"
            }
        }
    } catch {}

    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $versionFromName = Get-VersionFromName $baseName
    if ($versionFromName) { return "v$versionFromName" }
    return "-"
}

function Convert-ToMarkdownCell {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    return (($Text -replace '\|', '\|') -replace "`r?`n", " ")
}

function Add-SystemHistoryLogEntry {
    param(
        [string]$SourcePath,
        [string]$SnapshotDir,
        [string]$SnapshotName,
        [string]$DisplayTimestamp,
        [string]$WorkspaceRoot,
        [string]$HistoryRoot
    )

    $systemHistoryDir = Join-Path $HistoryRoot ".system"
    $logPath = Join-Path $systemHistoryDir "更新日志.md"
    Ensure-Directory $systemHistoryDir

    if (-not (Test-Path -LiteralPath $logPath)) {
        $title = @"
# .system 更新日志

> 记录 `.history/.system/{文件夹}_{yyyyMMddHHmmss}/` 每次快照对应的文件、版本和变更内容。备份脚本只知道修改前状态；修改完成后必须补全“修改后版本”和“变更内容”。

---

"@
        [System.IO.File]::WriteAllText($logPath, $title, [System.Text.UTF8Encoding]::new($false))
    }

    $sourceRel = Get-RelativePath -Path $SourcePath -Root $WorkspaceRoot
    $snapshotRel = Get-RelativePath -Path $SnapshotDir -Root $WorkspaceRoot
    $rows = @()
    $snapshotFiles = @(Get-ChildItem -LiteralPath $SnapshotDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne ".gitkeep" } |
        Sort-Object FullName)

    foreach ($file in $snapshotFiles) {
        $fileRel = Get-RelativePath -Path $file.FullName -Root $SnapshotDir
        $fileRel = $fileRel -replace '\\', '/'
        $version = Get-DeclaredVersionFromFile -Path $file.FullName
        $fileCell = Convert-ToMarkdownCell $fileRel
        $versionCell = Convert-ToMarkdownCell $version
        $rows += "| ``$fileCell`` | $versionCell | 待填写 | 待填写 |"
    }

    if ($rows.Count -eq 0) {
        $rows += "| （无文件） | - | - | - |"
    }

    $entry = @"
## $SnapshotName

- 备份时间：$DisplayTimestamp
- 源路径：``$sourceRel``
- 快照路径：``$snapshotRel``
- 记录状态：待补全

| 文件 | 备份时版本 | 修改后版本 | 变更内容 |
|------|------------|------------|----------|
$($rows -join "`r`n")

---

"@

    $current = [System.IO.File]::ReadAllText($logPath, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($logPath, $current + $entry, [System.Text.UTF8Encoding]::new($false))
    Write-Host "[OK] System history log updated: $logPath"
}

function Get-RootHistoryFolderName {
    param([System.IO.FileInfo]$FileItem)

    if (-not [string]::IsNullOrWhiteSpace($FileItem.BaseName)) {
        return $FileItem.BaseName
    }
    return ($FileItem.Name -replace '[^\p{L}\p{Nd}\._-]', '_').Trim('.')
}

function Get-SkillDisplayName {
    param([string]$SkillFolderPath)

    $openAiYaml = Join-Path $SkillFolderPath "agents\openai.yaml"
    if (-not (Test-Path -LiteralPath $openAiYaml)) {
        return $null
    }

    try {
        $content = Get-Content -LiteralPath $openAiYaml -Raw -Encoding UTF8
        if ($content -match '(?m)^\s*display_name:\s*["'']?(?<value>[^"''\r\n]+)["'']?\s*$') {
            return $Matches["value"].Trim()
        }
    } catch {}

    return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Find-WorkspaceRoot $scriptDir

if (-not $workspaceRoot) {
    Write-Error "Workspace root not found from script path (expected .agents and .history in project root)."
    exit 1
}

$originalTargetPath = $TargetPath
$TargetPath = Resolve-ProjectPath -Path $TargetPath -WorkspaceRoot $workspaceRoot

if (-not (Test-Path -LiteralPath $TargetPath)) {
    Write-Error "Target not found: $originalTargetPath"
    exit 1
}

$item = Get-Item -LiteralPath $TargetPath
$normalizedTarget = Normalize-PathString $TargetPath

$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$displayTimestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$historyRoot = Join-Path $workspaceRoot ".history"
$memoryKind = Get-MemoryKind -Path $TargetPath -WorkspaceRoot $workspaceRoot

if ($Mode -eq "AUTO") {
    if ($item.PSIsContainer) {
        if ($memoryKind -eq "MEMORY_FOLDER") {
            Write-Error "Folder snapshots under .memory are forbidden. Use file-level MEMORY backups only."
            exit 1
        }
        if ($normalizedTarget -match '\\output\\') {
            $Mode = "PROJECT"
        } else {
            $Mode = "FOLDER"
        }
    } elseif ($normalizedTarget -match '\\\.agents\\rules\\') {
        $Mode = "CONFIG"
    } elseif ($memoryKind -eq "APPEND_ONLY") {
        Write-Error "Append-only memory files do not use backup.ps1."
        exit 1
    } elseif ($memoryKind -eq "VERSIONED_COPY") {
        Write-Error "Versioned memory copies (*_v*.md) must not be used as live files. Move them out of .memory or use the stable file instead."
        exit 1
    } elseif ($memoryKind -like "VERSIONED*") {
        $Mode = "MEMORY"
    } elseif ($normalizedTarget -match '\\output\\') {
        Write-Error "output/ files must be backed up via PROJECT mode on the parent subproject folder, not as individual files."
        exit 1
    } else {
        $Mode = "FILE"
    }
    Write-Host "[INFO] Auto-detected mode: $Mode"
}

if ($Mode -eq "PROJECT") {
    if (-not $item.PSIsContainer) {
        Write-Error "PROJECT mode only supports folders (subproject root directory)."
        exit 1
    }

    $folderItem = Get-Item $TargetPath
    $folderName = $folderItem.Name
    $projectFullName = Get-ProjectFullName $folderName
    $projectTopic = Get-ProjectTopic $folderName
    $versionRecordPath = Join-Path $TargetPath "版本记录.md"
    $currentVersion = Get-LatestProjectVersionFromRecord $versionRecordPath
    if (-not $currentVersion) {
        $currentVersion = Get-VersionFromName $folderName
    }
    if (-not $currentVersion) {
        $currentVersion = "1.0.0"
        Write-Host "[WARN] No project version found. Treating current as v$currentVersion"
    }

    if (-not $projectFullName) {
        Write-Error "Cannot parse project name from folder: $folderName. Expected format: {编号}_{主题}"
        exit 1
    }

    $newVersion = Bump-Version -CurrentVersion $currentVersion -Type $ChangeType
    $relativePath = Get-RelativePath -Path $TargetPath -Root $workspaceRoot
    $relativeParent = Split-Path $relativePath -Parent

    $historyBaseDir = Join-Path $historyRoot $relativeParent
    $historyTimestampDir = Join-Path $historyBaseDir "${projectFullName}_v${currentVersion}_${timestamp}"

    Ensure-Directory $historyBaseDir
    Copy-Item -Path $TargetPath -Destination $historyTimestampDir -Recurse -Force
    Write-Host "[OK] History snapshot: $historyTimestampDir"

    Update-VersionRecord -VersionRecordPath $versionRecordPath -NewVersion $newVersion -ChangeType $ChangeType -DisplayTimestamp $displayTimestamp -ProjectTopic $projectTopic
    Write-Host "[OK] Version record updated: $versionRecordPath"

    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Project Backup Complete"
    Write-Host "=========================================="
    Write-Host "  Source    : $TargetPath"
    Write-Host "  Snapshot  : $historyTimestampDir"
    Write-Host "  Live Path : $TargetPath"
    Write-Host "  Version   : v$currentVersion --> v$newVersion ($ChangeType)"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Next: edit files in the stable live folder, then fill in 版本记录.md"

    exit 0
}

if ($Mode -eq "FOLDER") {
    if ($memoryKind -eq "MEMORY_FOLDER") {
        Write-Error "Folder snapshots under .memory are forbidden in the new design."
        exit 1
    }

    $folderItem = Get-Item -LiteralPath $TargetPath
    $folderName = $folderItem.Name
    $relativePath = Get-RelativePath -Path $TargetPath -Root $workspaceRoot
    $relativeParent = Split-Path $relativePath -Parent
    $validFolderTarget = ($relativePath -match '^\.agents\\skills\\[^\\]+$') -or ($relativePath -match '^\.system\\[^\\]+$')
    if (-not $validFolderTarget) {
        Write-Error "FOLDER mode only supports one .agents/skills/<skill> folder or one .system/<folder>. Got: $relativePath"
        exit 1
    }

    $skillDisplayName = if ($relativePath -match '^\.agents\\skills\\[^\\]+$') { Get-SkillDisplayName -SkillFolderPath $TargetPath } else { $null }
    $snapshotBaseName = if ($skillDisplayName) { $skillDisplayName } else { $folderName }
    $snapshotName = "${snapshotBaseName}_${timestamp}"
    $snapshotDir = Join-Path (Join-Path $historyRoot $relativeParent) $snapshotName
    if ((Normalize-PathString $snapshotDir) -match '\\.history\\skills\\') {
        Write-Error "Invalid skill snapshot path. Skill backups must go under .history/.agents/skills/."
        exit 1
    }

    Ensure-Directory $snapshotDir
    Copy-Item -Path (Join-Path $TargetPath "*") -Destination $snapshotDir -Recurse -Force

    if ($relativePath -match '^\.system\\[^\\]+$') {
        Add-SystemHistoryLogEntry -SourcePath $TargetPath -SnapshotDir $snapshotDir -SnapshotName $snapshotName -DisplayTimestamp $displayTimestamp -WorkspaceRoot $workspaceRoot -HistoryRoot $historyRoot
    }

    Write-Host "[OK] Folder snapshot created: $snapshotDir"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Folder Snapshot Complete"
    Write-Host "=========================================="
    Write-Host "  Source   : $TargetPath"
    Write-Host "  Snapshot : $snapshotDir"
    Write-Host "=========================================="
    exit 0
}

if ($Mode -eq "CONFIG") {
    if ($item.PSIsContainer) {
        Write-Error "CONFIG mode only supports files."
        exit 1
    }

    $fileItem = Get-Item $TargetPath
    $baseName = $fileItem.BaseName
    $ext = $fileItem.Extension
    $relativePath = Get-RelativePath -Path $TargetPath -Root $workspaceRoot
    $relativeParent = Split-Path $relativePath -Parent
    $historyFolderName = $baseName
    if ([string]::IsNullOrWhiteSpace($relativeParent)) {
        $historyFolderName = Get-RootHistoryFolderName -FileItem $fileItem
        $backupDir = Join-Path $historyRoot $historyFolderName
        $backupFileName = "${historyFolderName}_${timestamp}${ext}"
    } else {
        $backupDir = Join-Path $historyRoot $relativeParent
        $backupFileName = "${baseName}_${timestamp}${ext}"
    }
    $backupPath = Join-Path $backupDir $backupFileName

    Ensure-Directory $backupDir
    Copy-Item -Path $TargetPath -Destination $backupPath -Force

    Write-Host "[OK] Config file backed up: $backupPath"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Config Backup Complete"
    Write-Host "=========================================="
    Write-Host "  Source : $TargetPath"
    Write-Host "  Backup : $backupPath"
    Write-Host "=========================================="
    exit 0
}

if ($Mode -eq "MEMORY") {
    if ($item.PSIsContainer) {
        Write-Error "MEMORY mode only supports files."
        exit 1
    }

    if ($memoryKind -eq "APPEND_ONLY") {
        Write-Error "Append-only memory files must not be version-backed."
        exit 1
    }

    if ($memoryKind -eq "VERSIONED_COPY") {
        Write-Error "Versioned memory copies (*_v*.md) must not be version-backed. Use the stable .memory file instead."
        exit 1
    }

    if ($memoryKind -notlike "VERSIONED*") {
        Write-Error "MEMORY mode only supports versioned .memory files."
        exit 1
    }

    $fileItem = Get-Item $TargetPath
    $fileExt = $fileItem.Extension
    $fileBaseName = $fileItem.BaseName
    $pureName = Get-PureName $fileBaseName
    $currentVersion = Get-MemoryVersionFromContent $TargetPath

    if (-not $currentVersion) {
        $currentVersion = Get-VersionFromName $fileBaseName
    }
    if (-not $currentVersion) {
        $currentVersion = "1.0.0"
        Write-Host "[WARN] No memory version metadata found. Treating current as v$currentVersion"
    }

    $newVersion = Bump-Version -CurrentVersion $currentVersion -Type $ChangeType

    $relativePath = Get-RelativePath -Path $TargetPath -Root $workspaceRoot
    $parts = $relativePath -split '\\'

    if ($parts.Count -eq 2) {
        $historyDir = Join-Path $historyRoot (Join-Path ".memory" $pureName)
    } else {
        $historyDir = Join-Path $historyRoot (Join-Path ".memory" $parts[1])
    }

    $backupFileName = "${pureName}_v${currentVersion}${fileExt}"
    $backupPath = Join-Path $historyDir $backupFileName

    Ensure-Directory $historyDir
    Copy-Item -Path $TargetPath -Destination $backupPath -Force
    Set-MemoryVersionHeader -Path $TargetPath -NewVersion $newVersion

    Write-Host "[OK] Memory snapshot created: $backupPath"
    Write-Host "[OK] Live memory file kept stable: $TargetPath"
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  Memory Backup Complete"
    Write-Host "=========================================="
    Write-Host "  Source    : $TargetPath"
    Write-Host "  Snapshot  : $backupPath"
    Write-Host "  Live File : $TargetPath"
    Write-Host "  Version   : v$currentVersion --> v$newVersion ($ChangeType)"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Next: edit the stable live file in place"
    exit 0
}

if ($Mode -eq "FILE") {
    if ($normalizedTarget -match '\\output\\') {
        Write-Error "FILE mode is no longer used for output/ paths. Use PROJECT mode on the parent subproject folder instead."
        exit 1
    }

    if ($item.PSIsContainer) {
        Write-Error "FILE mode only supports files."
        exit 1
    }

    $fileItem = Get-Item $TargetPath
    $fileDir = $fileItem.DirectoryName
    $fileExt = $fileItem.Extension
    $fileBaseName = $fileItem.BaseName
    $relativePath = Get-RelativePath -Path $TargetPath -Root $workspaceRoot
    $currentVersion = Get-VersionFromName $fileBaseName
    $pureName = Get-PureName $fileBaseName
    $sourceHasVersion = [bool](Get-VersionFromName $fileBaseName)

    if (-not $currentVersion) {
        $currentVersion = "1.0.0"
        Write-Host "[WARN] No version in filename. Treating current as v$currentVersion"
    }

    $newVersion = Bump-Version -CurrentVersion $currentVersion -Type $ChangeType
    $historyRelDir = Split-Path $relativePath -Parent
    $historyFileDir = Join-Path $historyRoot $historyRelDir
    $historyFileName = if ($sourceHasVersion) { "$fileBaseName$fileExt" } else { "${pureName}_v${currentVersion}${fileExt}" }
    $historyFilePath = Join-Path $historyFileDir $historyFileName
    $newVersionFileName = "${pureName}_v${newVersion}${fileExt}"
    $newVersionFilePath = Join-Path $fileDir $newVersionFileName

    Ensure-Directory $historyFileDir
    Copy-Item -Path $TargetPath -Destination $historyFilePath -Force
    Write-Host "[OK] Backed up to: $historyFilePath"

    Move-Item -LiteralPath $TargetPath -Destination $newVersionFilePath -Force -ErrorAction Stop
    Write-Host "[OK] Renamed to:   $newVersionFilePath"

    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  File Version Backup Complete"
    Write-Host "=========================================="
    Write-Host "  Source   : $TargetPath"
    Write-Host "  Backup   : $historyFilePath"
    Write-Host "  New File : $newVersionFilePath"
    Write-Host "  Version  : v$currentVersion --> v$newVersion ($ChangeType)"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "Next: edit the new file: $newVersionFileName"
    exit 0
}

Write-Error "Unknown mode: $Mode"
exit 1
