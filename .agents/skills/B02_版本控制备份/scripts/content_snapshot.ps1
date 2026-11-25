# Working-content snapshot and SSOT backup policy helpers shared by B02 and B06.
function Get-WorkspaceBackupPolicy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    $specPath = Join-Path $WorkspaceRoot '.system\standards\workspace-spec.json'
    if (Test-Path -LiteralPath $specPath -PathType Leaf) {
        try {
            $raw = [System.IO.File]::ReadAllText($specPath, [System.Text.UTF8Encoding]::new($false))
            $spec = $raw | ConvertFrom-Json
        } catch {
            throw "Failed to parse SSOT workspace-spec.json at '$specPath': $($_.Exception.Message)"
        }
        if ($null -ne $spec -and $null -ne $spec.backupPolicy) {
            return $spec.backupPolicy
        }
    }

    Write-Host "[WARN] backupPolicy not found in .system/standards/workspace-spec.json; using built-in SSOT fallback."
    return [pscustomobject]@{
        project = [pscustomobject]@{
            mode = 'PROJECT'
            targetPattern = '^output\\[^\\]+$'
            includeSubfolders = @('01_问题答疑', '02_课题研究')
            includeRootFiles = $false
            exemptSubfolders = @('03_代码程序')
            triggerOn = @('01_问题答疑', '02_课题研究')
            versionRecordFile = '版本记录.md'
            historyBase = '.history/output'
        }
        memory = [pscustomobject]@{
            mode = 'MEMORY'
            versionedPaths = @('.memory/知识提炼/*.md', '.memory/全局知识地图.md')
            exemptDirs = @('.memory/对话记录', '.memory/系统记录', '.memory/任务进度')
        }
        folder = [pscustomobject]@{
            allowedTargets = @()
        }
        config = [pscustomobject]@{
            exemptPrefixes = @('.agents/rules', '.system')
        }
        exemptPaths = @(
            [pscustomobject]@{ path = 'output/*/03_代码程序'; reason = '子项目代码程序由独立 Git 或工具链管理，不触发也不进入 B02 快照' },
            [pscustomobject]@{ path = '.agents/skills'; reason = '核心骨架 Git 仓库已跟踪，免 B02 备份' },
            [pscustomobject]@{ path = '.agents/rules'; reason = '核心骨架 Git 仓库已跟踪，免 B02 备份' },
            [pscustomobject]@{ path = '.system'; reason = '核心骨架 Git 仓库已跟踪，免 B02 备份' },
            [pscustomobject]@{ path = '.memory/对话记录'; reason = '追加型记忆，不做版本备份' },
            [pscustomobject]@{ path = '.memory/系统记录'; reason = '追加型记忆，不做版本备份' },
            [pscustomobject]@{ path = '.memory/任务进度'; reason = 'B08 运行态任务进度，不做版本备份' }
        )
    }
}

# Refuse private credentials before creating any ordinary snapshot data.
function Assert-EnvironmentBackupPath {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $name = [IO.Path]::GetFileName($full.TrimEnd('\'))
    if ($name -ieq '.env' -or $name -like '*.env') {
        throw 'Private environment files require a separate encrypted credential backup.'
    }
    $match = [regex]::Match($full, '(?i)(^|\\)\.envs(?:\\|$)')
    if (-not $match.Success) { return }
    $relative = $full.Substring($match.Index + $match.Length).Replace('\', '/')
    if (Test-Path -LiteralPath $full -PathType Container) {
        if ($relative -notin @('', 'examples')) {
            throw 'Unmanaged environment directory cannot enter ordinary history.'
        }
        return
    }
    if ($relative -in @('.gitignore', 'README.md', 'catalog.json', 'env_manager.py')) { return }
    if ($relative -match '^examples/[a-z][a-z0-9.-]*\.env\.example$') {
        $text = [IO.File]::ReadAllText($full, [Text.Encoding]::UTF8)
        foreach ($line in ($text -split '\r?\n')) {
            if ($line -match '^\s*(#.*)?$') { continue }
            if ($line -notmatch '^\s*[A-Z][A-Z0-9_]*\s*=\s*(#.*)?$') {
                throw 'Only blank environment examples may enter ordinary history.'
            }
        }
        return
    }
    throw 'Private or unmanaged environment files cannot enter ordinary history.'
}

# Working-content snapshots deliberately exclude .git files and directories.
# No gitignore filtering: dirty, untracked, ignored and hidden files inside included trees are protected.
function Assert-SnapshotPlainPath {
    param([string]$Path)
    $cursor = [System.IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Snapshot cannot traverse a symbolic link or junction: $cursor"
            }
        }
        $parent = Split-Path $cursor -Parent
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function ConvertTo-TopLevelNameSet {
    param([string[]]$Names)
    $set = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    if ($null -ne $Names) {
        foreach ($n in $Names) {
            if (-not [string]::IsNullOrWhiteSpace($n)) {
                [void]$set.Add($n.Trim())
            }
        }
    }
    return ,$set
}

function New-ContentSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$IncludeTopLevelDirs = @(),
        [string[]]$ExcludeTopLevelDirs = @()
    )
    $includeSet = ConvertTo-TopLevelNameSet $IncludeTopLevelDirs
    $excludeSet = ConvertTo-TopLevelNameSet $ExcludeTopLevelDirs
    if ($includeSet.Count -gt 0 -and $excludeSet.Count -gt 0) {
        throw 'IncludeTopLevelDirs and ExcludeTopLevelDirs cannot be combined.'
    }

    $sourceFull = [System.IO.Path]::GetFullPath($Source).TrimEnd('\')
    $destinationFull = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
    if ($destinationFull.Equals($sourceFull, [System.StringComparison]::OrdinalIgnoreCase) -or
        $destinationFull.StartsWith($sourceFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Snapshot destination must be outside its source tree.'
    }
    Assert-EnvironmentBackupPath $sourceFull
    Assert-SnapshotPlainPath $sourceFull
    Assert-SnapshotPlainPath $destinationFull
    if (-not (Test-Path -LiteralPath $sourceFull -PathType Container)) {
        throw "Snapshot source directory not found: $sourceFull"
    }
    if (Test-Path -LiteralPath $destinationFull) {
        throw "Snapshot already exists; refusing to overwrite: $destinationFull"
    }

    # Preflight the selected payload before creating a snapshot. Never silently skip links in included trees.
    $entries = [System.Collections.Generic.List[object]]::new()
    $queue = [System.Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($sourceFull)
    $excluded = 0
    $matchedTopDirs = 0
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        $isTopLevel = $directory.Equals($sourceFull, [System.StringComparison]::OrdinalIgnoreCase)
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            if ($item.Name -ieq '.git') { $excluded++; continue }
            if ($isTopLevel) {
                if ($includeSet.Count -gt 0) {
                    if (-not $includeSet.Contains($item.Name)) { continue }
                    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                        throw "Snapshot cannot protect link contents automatically: $($item.FullName)"
                    }
                    if (-not $item.PSIsContainer) { continue }
                    $matchedTopDirs++
                } elseif ($excludeSet.Count -gt 0 -and $item.PSIsContainer -and $excludeSet.Contains($item.Name)) {
                    continue
                }
            }
            Assert-EnvironmentBackupPath $item.FullName
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                throw "Snapshot cannot protect link contents automatically: $($item.FullName)"
            }
            $entries.Add([pscustomobject]@{
                Source = $item.FullName
                Relative = $item.FullName.Substring($sourceFull.Length + 1)
                IsDirectory = $item.PSIsContainer
            })
            if ($item.PSIsContainer) { $queue.Enqueue($item.FullName) }
        }
    }

    if ($includeSet.Count -gt 0 -and $matchedTopDirs -eq 0) {
        throw "Snapshot source does not contain any configured backup subdirectories ($($IncludeTopLevelDirs -join ', ')): $sourceFull"
    }

    $parent = Split-Path $destinationFull -Parent
    [System.IO.Directory]::CreateDirectory($parent) | Out-Null
    $pending = $destinationFull + '.incomplete-' + [guid]::NewGuid().ToString('N')
    [System.IO.Directory]::CreateDirectory($pending) | Out-Null
    try {
        foreach ($entry in $entries) {
            # Recheck to catch files replaced by links after the preflight.
            Assert-SnapshotPlainPath $entry.Source
            $target = Join-Path $pending $entry.Relative
            if ($entry.IsDirectory) {
                [System.IO.Directory]::CreateDirectory($target) | Out-Null
            } else {
                Copy-Item -LiteralPath $entry.Source -Destination $target -Force -ErrorAction Stop
            }
        }
        # Windows indexers can briefly hold the copied tree without delete sharing.
        # Retry publication only; never recopy, overwrite, or advance live versions early.
        for ($publishAttempt = 0; ; $publishAttempt++) {
            try {
                [System.IO.Directory]::Move($pending, $destinationFull)
                break
            } catch [System.UnauthorizedAccessException] {
                if ($publishAttempt -ge 5) { throw }
                Start-Sleep -Milliseconds 1000
            } catch [System.IO.IOException] {
                if ($publishAttempt -ge 5 -or (Test-Path -LiteralPath $destinationFull)) { throw }
                Start-Sleep -Milliseconds 1000
            }
        }
    } catch {
        # Preserve diagnostic partial data; never publish success or mutate live versions.
        throw "Snapshot failed; incomplete data retained at '$pending': $($_.Exception.Message)"
    }
    Write-Host "[OK] Working-content snapshot; excluded $excluded Git metadata entries: $destinationFull"
}


# Only the official backup entrypoint selects PROJECT recovery destinations.
function ConvertTo-SnapshotExtendedPath {
    param([string]$Path)
    $full = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($full.StartsWith('\\?\')) { return $full }
    if ($full.StartsWith('\\')) { return '\\?\UNC\' + $full.Substring(2) }
    if ($env:OS -eq 'Windows_NT') { return '\\?\' + $full }
    return $full
}

function Assert-RecoveryPlainPath {
    param([string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        $native = ConvertTo-SnapshotExtendedPath $cursor
        if ([IO.Directory]::Exists($native) -or [IO.File]::Exists($native)) {
            if ([IO.File]::GetAttributes($native) -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Snapshot recovery refuses symbolic links and junctions.'
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor.TrimEnd('\'))
        if (-not $parent -or $parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function Get-RecoverySnapshotManifest {
    param(
        [string]$Root,
        [switch]$ExcludeGit,
        [string[]]$IncludeTopLevelDirs = @(),
        [string[]]$ExcludeTopLevelDirs = @()
    )
    $includeSet = ConvertTo-TopLevelNameSet $IncludeTopLevelDirs
    $excludeSet = ConvertTo-TopLevelNameSet $ExcludeTopLevelDirs
    if ($includeSet.Count -gt 0 -and $excludeSet.Count -gt 0) {
        throw 'IncludeTopLevelDirs and ExcludeTopLevelDirs cannot be combined.'
    }

    Assert-RecoveryPlainPath $Root
    $nativeRoot = ConvertTo-SnapshotExtendedPath $Root
    if (-not [IO.Directory]::Exists($nativeRoot)) { throw 'Recovery tree is missing.' }
    $manifest = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($nativeRoot)
    $matchedTopDirs = 0
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        $isTopLevel = $directory.Equals($nativeRoot, [StringComparison]::OrdinalIgnoreCase)
        foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($directory)) {
            $entryName = [IO.Path]::GetFileName($entry)
            if ($entryName -ieq '.git') {
                if ($ExcludeGit) { continue }
                throw 'Pending snapshot unexpectedly contains Git metadata.'
            }
            $attributes = [IO.File]::GetAttributes($entry)
            if ($isTopLevel) {
                if ($includeSet.Count -gt 0) {
                    if (-not $includeSet.Contains($entryName)) { continue }
                    if ($attributes -band [IO.FileAttributes]::ReparsePoint) {
                        throw 'Recovery tree contains a symbolic link or junction.'
                    }
                    if (-not ($attributes -band [IO.FileAttributes]::Directory)) { continue }
                    $matchedTopDirs++
                } elseif ($excludeSet.Count -gt 0 -and ($attributes -band [IO.FileAttributes]::Directory) -and $excludeSet.Contains($entryName)) {
                    continue
                }
            }
            Assert-EnvironmentBackupPath $entry
            if ($attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Recovery tree contains a symbolic link or junction.'
            }
            $relative = $entry.Substring($nativeRoot.Length + 1)
            if ($attributes -band [IO.FileAttributes]::Directory) {
                $manifest.Add($relative, 'DIRECTORY')
                $queue.Enqueue($entry)
            } else {
                # Deny new writers while this file is being hashed; never log contents.
                $stream = [IO.File]::Open($entry, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
                try {
                    $length = $stream.Length
                    $sha = [Security.Cryptography.SHA256]::Create()
                    try { $digest = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
                    finally { $sha.Dispose() }
                    $manifest.Add($relative, ('FILE:' + $length + ':' + $digest))
                } finally { $stream.Dispose() }
            }
        }
    }
    if ($includeSet.Count -gt 0 -and $matchedTopDirs -eq 0) {
        throw 'Recovery source does not contain any configured backup subdirectories.'
    }
    return ,$manifest
}

function Assert-RecoveryManifestEqual {
    param($Expected, $Actual)
    if ($Expected.Count -ne $Actual.Count) { throw 'Recovery manifests differ in entry count.' }
    foreach ($relative in $Expected.Keys) {
        if (-not $Actual.ContainsKey($relative) -or $Expected[$relative] -cne $Actual[$relative]) {
            throw 'Recovery manifests differ in path, entry type, length or SHA256.'
        }
    }
}

function Complete-ContentSnapshot {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Pending,
        [Parameter(Mandatory=$true)][string]$Destination,
        [string[]]$IncludeTopLevelDirs = @(),
        [string[]]$ExcludeTopLevelDirs = @()
    )
    # Caller validates workspace/project/version/name. Recheck all traversed paths here.
    Assert-RecoveryPlainPath $Source
    Assert-RecoveryPlainPath $Pending
    Assert-RecoveryPlainPath $Destination
    $nativePending = ConvertTo-SnapshotExtendedPath $Pending
    $nativeDestination = ConvertTo-SnapshotExtendedPath $Destination
    if ([IO.Directory]::Exists($nativeDestination) -or [IO.File]::Exists($nativeDestination)) {
        throw 'Recovery destination already exists; refusing to overwrite.'
    }
    $sourceBefore = Get-RecoverySnapshotManifest -Root $Source -ExcludeGit -IncludeTopLevelDirs $IncludeTopLevelDirs -ExcludeTopLevelDirs $ExcludeTopLevelDirs
    $pendingManifest = Get-RecoverySnapshotManifest -Root $Pending
    Assert-RecoveryManifestEqual $sourceBefore $pendingManifest
    # Catch changes during the full hash pass. Callers must keep source writers quiescent.
    $sourceAfter = Get-RecoverySnapshotManifest -Root $Source -ExcludeGit -IncludeTopLevelDirs $IncludeTopLevelDirs -ExcludeTopLevelDirs $ExcludeTopLevelDirs
    Assert-RecoveryManifestEqual $sourceBefore $sourceAfter
    Assert-RecoveryPlainPath $Pending
    Assert-RecoveryPlainPath $Destination
    for ($attempt = 0; ; $attempt++) {
        try {
            [IO.Directory]::Move($nativePending, $nativeDestination)
            break
        } catch [UnauthorizedAccessException] {
            if ($attempt -ge 5) { throw }
            Start-Sleep -Milliseconds 1000
        } catch [IO.IOException] {
            if ($attempt -ge 5 -or [IO.Directory]::Exists($nativeDestination) -or [IO.File]::Exists($nativeDestination)) { throw }
            Start-Sleep -Milliseconds 1000
        }
    }
    Write-Host ('[OK] Verified and published complete pending snapshot; entries: ' + $sourceBefore.Count)
}
