<#
.SYNOPSIS
    Manage resumable task progress files under .memory/task progress area.
.DESCRIPTION
    Creates, updates, resumes, and closes task progress records.
    The script is intentionally small and deterministic so agents do not hand-edit index files.
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Start", "Checkpoint", "UpdateNext", "Pause", "Close", "Resume")]
    [string]$Action,

    [string]$TaskId,
    [string]$Title,
    [string]$Goal,
    [string]$Next,
    [string]$Message,
    [string]$Reason,
    [string]$Result,
    [string]$Files,
    [string]$Owner = "Codex",

    [ValidateSet("ACTIVE", "PAUSED", "BLOCKED", "REVIEW", "DONE", "CANCELED", "STALE")]
    [string]$Status
)

chcp 65001 > $null
$ErrorActionPreference = "Stop"

function Find-WorkspaceRoot {
    param([string]$StartPath)
    $searchDir = [System.IO.Path]::GetFullPath($StartPath)
    while ($searchDir) {
        if ((Test-Path -LiteralPath (Join-Path $searchDir ".history")) -and
            (Test-Path -LiteralPath (Join-Path $searchDir ".memory"))) {
            return $searchDir
        }
        $parent = Split-Path $searchDir -Parent
        if ($parent -eq $searchDir) { break }
        $searchDir = $parent
    }
    throw "Workspace root not found."
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Write-Utf8File {
    param([string]$Path, [string]$Content)
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Read-Utf8File {
    param([string]$Path)
    return [System.IO.File]::ReadAllText($Path, [System.Text.UTF8Encoding]::new($false))
}

function Get-NowText {
    return (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
}

function Get-NowIdText {
    return (Get-Date -Format "yyyyMMdd-HHmm")
}

function Convert-ToSafeTitle {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return "未命名任务" }
    $safe = $Text.Trim() -replace '[\\/:*?"<>|]', ''
    $safe = $safe -replace '\s+', ''
    if ($safe.Length -gt 24) { $safe = $safe.Substring(0, 24) }
    if ([string]::IsNullOrWhiteSpace($safe)) { return "未命名任务" }
    return $safe
}

function New-TaskId {
    param([string]$TaskTitle)
    return "T$(Get-NowIdText)-$(Convert-ToSafeTitle $TaskTitle)"
}

function Initialize-ProgressArea {
    Ensure-Directory $script:ProgressRoot
    Ensure-Directory $script:ActiveDir
    Ensure-Directory $script:DoneDir
    Ensure-Directory $script:CanceledDir
    if (-not (Test-Path -LiteralPath $script:IndexPath)) {
        Update-Index
    }
}

function Get-TaskFiles {
    param([switch]$All)
    $dirs = if ($All) { @($script:ActiveDir, $script:DoneDir, $script:CanceledDir) } else { @($script:ActiveDir) }
    $files = @()
    foreach ($dir in $dirs) {
        if (Test-Path -LiteralPath $dir) {
            $files += @(Get-ChildItem -LiteralPath $dir -Filter "*.md" -File -ErrorAction SilentlyContinue)
        }
    }
    return $files | Sort-Object @{ Expression = "LastWriteTime"; Descending = $true }, Name
}

function Find-TaskFile {
    param([string]$Id)
    if ([string]::IsNullOrWhiteSpace($Id)) { throw "TaskId is required for $Action." }
    $matches = @(Get-TaskFiles -All | Where-Object { $_.BaseName -like "$Id*" })
    if ($matches.Count -eq 0) { throw "Task not found: $Id" }
    if ($matches.Count -gt 1) { throw "Multiple tasks match: $Id" }
    return $matches[0].FullName
}

function Get-TaskMeta {
    param([string]$Path)
    $content = Read-Utf8File $Path
    $title = ""
    $taskId = ""
    $status = ""
    $updatedAt = ""
    $current = ""
    if ($content -match '(?m)^# 任务进度 · (.+)$') { $title = $Matches[1].Trim() }
    if ($content -match '(?m)^> task-id:\s*(.+)$') { $taskId = $Matches[1].Trim() }
    if ($content -match '(?m)^> status:\s*(.+)$') { $status = $Matches[1].Trim() }
    if ($content -match '(?m)^> updated-at:\s*(.+)$') { $updatedAt = $Matches[1].Trim() }
    if ($content -match '(?m)^\*\*当前状态\*\*：(.+)$') { $current = $Matches[1].Trim() }
    return [PSCustomObject]@{
        Title = $title
        TaskId = $taskId
        Status = $status
        UpdatedAt = $updatedAt
        Current = $current
        Path = $Path
    }
}

function Update-MetaLine {
    param([string]$Content, [string]$Key, [string]$Value)
    return [regex]::Replace($Content, "(?m)^> $([regex]::Escape($Key)):\s*.*$", "> ${Key}: $Value")
}

function Update-CardLine {
    param([string]$Content, [string]$Label, [string]$Value)
    return [regex]::Replace($Content, "(?m)^\*\*$([regex]::Escape($Label))\*\*：.*$", "**${Label}**：$Value")
}

function Add-EventRow {
    param([string]$Content, [string]$Type, [string]$Text)
    $row = "| $(Get-NowText) | $Type | $($Text -replace "`r?`n", " ") |"
    return [regex]::Replace(
        $Content,
        "(?s)(## 事件日志.*?\|------\|------\|------\|)",
        "`${1}`r`n$row",
        1
    )
}

function Add-FileRows {
    param([string]$Content, [string]$FileText)
    if ([string]::IsNullOrWhiteSpace($FileText)) { return $Content }
    $rows = @()
    foreach ($item in ($FileText -split ';')) {
        $trimmed = $item.Trim()
        if ($trimmed) { $rows += "| $trimmed | touched | 任务进度记录 |" }
    }
    if ($rows.Count -eq 0) { return $Content }
    $joined = ($rows -join "`r`n")
    return [regex]::Replace(
        $Content,
        "(?s)(## 文件与产物.*?\|------\|------\|------\|)",
        "`${1}`r`n$joined",
        1
    )
}

function Save-TaskContent {
    param([string]$Path, [string]$Content)
    $updated = Update-MetaLine -Content $Content -Key "updated-at" -Value (Get-NowText)
    Write-Utf8File -Path $Path -Content $updated
}

function Update-Index {
    $activeTasks = @(Get-TaskFiles | ForEach-Object { Get-TaskMeta $_.FullName } |
        Where-Object { $_.Status -in @("ACTIVE", "PAUSED", "BLOCKED", "REVIEW", "STALE") } |
        Sort-Object @{ Expression = "UpdatedAt"; Descending = $true }, TaskId)
    $doneCount = @(Get-ChildItem -LiteralPath $script:DoneDir -Filter "*.md" -File -ErrorAction SilentlyContinue).Count
    $canceledCount = @(Get-ChildItem -LiteralPath $script:CanceledDir -Filter "*.md" -File -ErrorAction SilentlyContinue).Count

    $rows = @()
    foreach ($task in $activeTasks) {
        $rel = $task.Path.Substring($script:WorkspaceRoot.Length + 1) -replace '\\', '/'
        $rows += "| $($task.TaskId) | $($task.Status) | $($task.UpdatedAt) | [$([System.IO.Path]::GetFileName($task.Path))]($rel) | $($task.Current) |"
    }
    if ($rows.Count -eq 0) {
        $rows += "| - | - | - | - | 当前没有待恢复任务 |"
    }

    $content = @"
# 任务进度索引

> 恢复入口。列出当前需要继续关注的任务，详细过程进入各任务文件。

更新时间：$(Get-NowText)

---

## 当前任务

| task-id | status | updated-at | 文件 | 当前状态 |
|------|------|------|------|------|
$($rows -join "`r`n")

---

## 历史区

| 类型 | 数量 | 目录 |
|------|------|------|
| 已完成 | $doneCount | `.memory/任务进度/已完成/` |
| 已取消 | $canceledCount | `.memory/任务进度/已取消/` |
"@
    Write-Utf8File -Path $script:IndexPath -Content ($content + "`r`n")
}

function Start-Task {
    if ([string]::IsNullOrWhiteSpace($Title)) { throw "Title is required for Start." }
    $id = if ([string]::IsNullOrWhiteSpace($TaskId)) { New-TaskId $Title } else { $TaskId }
    $safeTitle = Convert-ToSafeTitle $Title
    $path = Join-Path $script:ActiveDir "$id.md"
    if (Test-Path -LiteralPath $path) { throw "Task already exists: $id" }
    $created = Get-NowText
    $goalText = if ([string]::IsNullOrWhiteSpace($Goal)) { $Title } else { $Goal }
    $nextText = if ([string]::IsNullOrWhiteSpace($Next)) { "继续执行任务并在关键步骤后写 checkpoint。" } else { $Next }

    $content = @"
# 任务进度 · $Title

> task-id: $id
> status: ACTIVE
> created-at: $created
> updated-at: $created
> owner: $Owner

---

## 恢复卡片

**用户目标**：$goalText
**当前状态**：任务已创建，准备执行。
**下一步**：$nextText
**最近安全点**：尚未记录。
**阻塞项**：无

---

## 执行计划

| 状态 | 步骤 | 说明 |
|------|------|------|
| doing | 执行任务 | 按用户目标推进，并在关键步骤后记录 checkpoint |

---

## 事件日志

| 时间 | 类型 | 事件 |
|------|------|------|
| $created | start | 任务创建：$Title |

---

## 文件与产物

| 路径 | 状态 | 说明 |
|------|------|------|

---

## 恢复指令

下次接手时：
1. 先读本文件的恢复卡片。
2. 再读事件日志最后 5 条。
3. 检查文件与产物列表中的路径是否仍存在。
4. 从“下一步”继续。

---

## 最终摘要

（未完成）
"@
    Write-Utf8File -Path $path -Content $content
    Update-Index
    Write-Host "task-id=$id"
    Write-Host "task-file=$path"
}

function Checkpoint-Task {
    $path = Find-TaskFile $TaskId
    $content = Read-Utf8File $path
    $messageText = if ([string]::IsNullOrWhiteSpace($Message)) { "checkpoint" } else { $Message }
    $newStatus = if ([string]::IsNullOrWhiteSpace($Status)) { "ACTIVE" } else { $Status }
    $content = Update-MetaLine -Content $content -Key "status" -Value $newStatus
    $content = Update-CardLine -Content $content -Label "当前状态" -Value $messageText
    $content = Add-EventRow -Content $content -Type "checkpoint" -Text $messageText
    $content = Add-FileRows -Content $content -FileText $Files
    Save-TaskContent -Path $path -Content $content
    Update-Index
    Write-Host "checkpoint=$TaskId"
}

function Update-TaskNext {
    $path = Find-TaskFile $TaskId
    if ([string]::IsNullOrWhiteSpace($Next)) { throw "Next is required for UpdateNext." }
    $content = Read-Utf8File $path
    $content = Update-CardLine -Content $content -Label "下一步" -Value $Next
    $content = Add-EventRow -Content $content -Type "next" -Text $Next
    Save-TaskContent -Path $path -Content $content
    Update-Index
    Write-Host "next-updated=$TaskId"
}

function Pause-Task {
    $path = Find-TaskFile $TaskId
    $reasonText = if ([string]::IsNullOrWhiteSpace($Reason)) { "等待继续" } else { $Reason }
    $newStatus = if ([string]::IsNullOrWhiteSpace($Status)) { "PAUSED" } else { $Status }
    if ($newStatus -notin @("PAUSED", "BLOCKED", "REVIEW", "STALE")) {
        throw "Pause supports PAUSED, BLOCKED, REVIEW, or STALE."
    }
    $content = Read-Utf8File $path
    $content = Update-MetaLine -Content $content -Key "status" -Value $newStatus
    $content = Update-CardLine -Content $content -Label "当前状态" -Value "已暂停：$reasonText"
    $content = Update-CardLine -Content $content -Label "阻塞项" -Value $reasonText
    $content = Add-EventRow -Content $content -Type "pause" -Text "$newStatus：$reasonText"
    Save-TaskContent -Path $path -Content $content
    Update-Index
    Write-Host "paused=$TaskId"
}

function Close-Task {
    $path = Find-TaskFile $TaskId
    $resultText = if ([string]::IsNullOrWhiteSpace($Result)) { "任务已关闭。" } else { $Result }
    $newStatus = if ([string]::IsNullOrWhiteSpace($Status)) { "DONE" } else { $Status }
    if ($newStatus -notin @("DONE", "CANCELED")) { throw "Close supports DONE or CANCELED." }
    $content = Read-Utf8File $path
    $content = Update-MetaLine -Content $content -Key "status" -Value $newStatus
    $content = Update-CardLine -Content $content -Label "当前状态" -Value $resultText
    $content = Update-CardLine -Content $content -Label "下一步" -Value "任务已关闭；如需恢复，先读最终摘要并由用户确认。"
    $content = Update-CardLine -Content $content -Label "阻塞项" -Value "无"
    $content = Add-EventRow -Content $content -Type "close" -Text "$newStatus：$resultText"
    $content = [regex]::Replace($content, "(?s)## 最终摘要\r?\n\r?\n.*$", "## 最终摘要`r`n`r`n$resultText`r`n")
    Save-TaskContent -Path $path -Content $content

    $destinationDir = if ($newStatus -eq "CANCELED") { $script:CanceledDir } else { $script:DoneDir }
    $destination = Join-Path $destinationDir ([System.IO.Path]::GetFileName($path))
    Move-Item -LiteralPath $path -Destination $destination -Force
    Update-Index
    Write-Host "closed=$TaskId"
    Write-Host "archive=$destination"
}

function Resume-Tasks {
    Update-Index
    Write-Host "index=$script:IndexPath"
    $tasks = @(Get-TaskFiles | ForEach-Object { Get-TaskMeta $_.FullName } |
        Where-Object { $_.Status -in @("ACTIVE", "PAUSED", "BLOCKED", "REVIEW", "STALE") } |
        Sort-Object @{ Expression = "UpdatedAt"; Descending = $true }, TaskId)
    if ($tasks.Count -eq 0) {
        Write-Host "active-tasks=0"
        return
    }
    foreach ($task in $tasks) {
        Write-Host "task=$($task.TaskId) status=$($task.Status) updated=$($task.UpdatedAt) file=$($task.Path)"
        Write-Host "current=$($task.Current)"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Find-WorkspaceRoot $scriptDir
$script:WorkspaceRoot = $workspaceRoot
$script:ProgressRoot = Join-Path $workspaceRoot ".memory\任务进度"
$script:ActiveDir = Join-Path $script:ProgressRoot "进行中"
$script:DoneDir = Join-Path $script:ProgressRoot "已完成"
$script:CanceledDir = Join-Path $script:ProgressRoot "已取消"
$script:IndexPath = Join-Path $script:ProgressRoot "索引.md"

Initialize-ProgressArea

switch ($Action) {
    "Start" { Start-Task }
    "Checkpoint" { Checkpoint-Task }
    "UpdateNext" { Update-TaskNext }
    "Pause" { Pause-Task }
    "Close" { Close-Task }
    "Resume" { Resume-Tasks }
}
