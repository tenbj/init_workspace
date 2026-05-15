<#
.SYNOPSIS
    Create a new sub-project folder under output/
.DESCRIPTION
    Creates a versioned sub-project directory following naming convention:
    output\{Number}_{Topic}_v1.0.0
    Inside the project, creates three sub-folders:
      01_问题答疑_v0.0.0\   (empty placeholder)
      02_课题研究_v0.0.0\   (empty placeholder)
      03_代码程序_v0.0.0\   (empty placeholder)
    Also initializes 版本记录.md and 目录.md (三节格式) inside.
.PARAMETER Topic
    The topic/domain name in Chinese (required)
.PARAMETER OutputRoot
    The root output directory. Defaults to the workspace output folder.
.EXAMPLE
    .\new_project.ps1 -Topic "减肥第一性原理"
    # Creates: output\01_减肥第一性原理_v1.0.0\
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Topic,

    [Parameter(Mandatory=$false)]
    [string]$OutputRoot = ""
)

$utf8WithBom = New-Object System.Text.UTF8Encoding $true
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-MemoryVersionFromText {
    param([string]$Text)
    if ($Text -match '<!--\s*memory-version:\s*(\d+)\.(\d+)\.(\d+)\s*-->') {
        return @{
            Text = "$($Matches[1]).$($Matches[2]).$($Matches[3])"
            Major = [int]$Matches[1]
            Minor = [int]$Matches[2]
            Patch = [int]$Matches[3]
        }
    }
    return @{
        Text = "1.0.0"
        Major = 1
        Minor = 0
        Patch = 0
    }
}

function Update-GlobalKnowledgeMap {
    param(
        [string]$WorkspaceRoot,
        [string]$Topic,
        [string]$FolderName
    )

    $memoryDir = Join-Path $WorkspaceRoot ".memory"
    $historyDir = Join-Path $WorkspaceRoot ".history\.memory\全局知识地图"
    $mapPath = Join-Path $memoryDir "全局知识地图.md"
    Ensure-Directory $memoryDir
    Ensure-Directory $historyDir

    $todayDate = Get-Date -Format "yyyy-MM-dd"
    $row = "| $Topic | $FolderName | $todayDate | 进行中 | - |"

    if (Test-Path -LiteralPath $mapPath) {
        $mapText = [System.IO.File]::ReadAllText($mapPath, $utf8NoBom)
        $oldVersion = Get-MemoryVersionFromText $mapText
        $snapshotPath = Join-Path $historyDir "全局知识地图_v$($oldVersion.Text).md"
        Copy-Item -LiteralPath $mapPath -Destination $snapshotPath -Force

        $newVersion = "$($oldVersion.Major).$($oldVersion.Minor + 1).0"
        $header = "<!-- memory-version: $newVersion -->"
        if ($mapText -match '^\s*<!--\s*memory-version:\s*\d+\.\d+\.\d+\s*-->') {
            $mapText = [regex]::Replace(
                $mapText,
                '^\s*<!--\s*memory-version:\s*\d+\.\d+\.\d+\s*-->',
                $header,
                1
            )
        } else {
            $mapText = "$header`r`n" + $mapText
        }
    } else {
        $mapText = @"
<!-- memory-version: 1.0.0 -->
# 全局知识地图

> 所有研究子项目的总索引，新建子项目时自动更新。

| 话题 | 子项目文件夹 | 创建时间 | 状态 | 核心结论（一句话） |
|------|------------|---------|------|----------------|
"@
    }

    if ($mapText -notmatch [regex]::Escape("| $Topic | $FolderName |")) {
        $mapText = $mapText.TrimEnd() + "`r`n$row`r`n"
    }

    [System.IO.File]::WriteAllText($mapPath, $mapText, $utf8WithBom)
    Write-Host "[OK] Updated global knowledge map: $mapPath"
}

function Initialize-ConversationRecord {
    param(
        [string]$WorkspaceRoot,
        [string]$Topic,
        [string]$FolderName
    )

    $convDir = Join-Path $WorkspaceRoot ".memory\对话记录"
    Ensure-Directory $convDir
    $convPath = Join-Path $convDir "$FolderName.md"
    if (Test-Path -LiteralPath $convPath) {
        return
    }

    $content = @"
# 对话记录 · $Topic

> 记录本子项目所有对话的关键摘要，按时间追加。

---

"@
    [System.IO.File]::WriteAllText($convPath, $content, $utf8WithBom)
    Write-Host "[OK] Created conversation record: $convPath"
}

$workspaceRoot = $null
if ($OutputRoot -eq "") {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $searchDir = $scriptDir
    while ($searchDir) {
        if ((Test-Path (Join-Path $searchDir "output")) -and (Test-Path (Join-Path $searchDir ".history"))) {
            $workspaceRoot = $searchDir
            break
        }
        $parent = Split-Path $searchDir -Parent
        if ($parent -eq $searchDir) { break }
        $searchDir = $parent
    }
    if (-not $workspaceRoot) {
        Write-Error "Workspace root not found. Please specify -OutputRoot explicitly."
        exit 1
    }
    $OutputRoot = Join-Path $workspaceRoot "output"
} else {
    $outputRootFull = [System.IO.Path]::GetFullPath($OutputRoot)
    $workspaceRoot = Split-Path -Parent $outputRootFull
}

$existingProjectNumbers = @(
    Get-ChildItem -Path $OutputRoot -Directory -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.Name -match '^(\d+)_') {
                [int]$matches[1]
            }
        }
) | Sort-Object -Descending

$nextProjectNumber = if ($existingProjectNumbers.Count -gt 0) {
    $existingProjectNumbers[0] + 1
} else {
    1
}

$projectNumber = "{0:D2}" -f $nextProjectNumber
$folderName = "${projectNumber}_${Topic}_v1.0.0"
$projectPath = Join-Path $OutputRoot $folderName

if (Test-Path $projectPath) {
    Write-Error "Folder already exists: $projectPath"
    exit 1
}

New-Item -ItemType Directory -Path $projectPath -Force | Out-Null
Write-Host "[OK] Created project folder: $projectPath"

# Create three sub-folders (empty placeholders v0.0.0)
$subFolders = @("01_问题答疑_v0.0.0", "02_课题研究_v0.0.0", "03_代码程序_v0.0.0")
foreach ($sf in $subFolders) {
    $sfPath = Join-Path $projectPath $sf
    New-Item -ItemType Directory -Path $sfPath -Force | Out-Null
    Write-Host "[OK] Created sub-folder: $sf"
}

$displayTimestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$versionRecordPath = Join-Path $projectPath "版本记录.md"
$versionRecordContent = @"
# 版本记录 · $Topic

> 记录子项目的版本变更历史。

---

## v1.0.0 ($displayTimestamp)

**变更类型**：MAJOR
**创建时间**：$displayTimestamp
**变更描述**：首次创建。

**子文件变更明细**：

| 文件 | 版本变更 | 变更描述 |
|------|---------|---------|
| （待填写） | | |

---

"@
[System.IO.File]::WriteAllText($versionRecordPath, $versionRecordContent, $utf8WithBom)
Write-Host "[OK] Created version record: $versionRecordPath"

$catalogPath = Join-Path $projectPath "目录.md"
$catalogContent = @"
# 目录 · $Topic

> 本子项目内所有内容文件的索引，按三个子文件夹分节列出。

---

## 01_问题答疑

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
| 待新增文件后填写 | | | | |

---

## 02_课题研究

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
| 待新增文件后填写 | | | | |

---

## 03_代码程序

| # | 文件 | 说明 | 首次落盘 | 最近更新 |
|---|------|------|---------|---------|
| 待新增文件后填写 | | | | |

"@
[System.IO.File]::WriteAllText($catalogPath, $catalogContent, $utf8WithBom)
Write-Host "[OK] Created catalog: $catalogPath"

Update-GlobalKnowledgeMap -WorkspaceRoot $workspaceRoot -Topic $Topic -FolderName $folderName
Initialize-ConversationRecord -WorkspaceRoot $workspaceRoot -Topic $Topic -FolderName $folderName

Write-Host ""
Write-Host "=========================================="
Write-Host "  New Sub-Project Created"
Write-Host "=========================================="
Write-Host "  Topic    : $Topic"
Write-Host "  Folder   : $folderName"
Write-Host "  Path     : $projectPath"
Write-Host "  Created  : $displayTimestamp"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next: create files inside sub-folders of $projectPath"
