# Working-content snapshots deliberately exclude .git files and directories.
# No gitignore filtering: dirty, untracked, ignored and hidden files are protected.
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

function New-ContentSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $sourceFull = [System.IO.Path]::GetFullPath($Source).TrimEnd('\')
    $destinationFull = [System.IO.Path]::GetFullPath($Destination).TrimEnd('\')
    if ($destinationFull.Equals($sourceFull, [System.StringComparison]::OrdinalIgnoreCase) -or
        $destinationFull.StartsWith($sourceFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Snapshot destination must be outside its source tree.'
    }
    Assert-SnapshotPlainPath $sourceFull
    Assert-SnapshotPlainPath $destinationFull
    if (-not (Test-Path -LiteralPath $sourceFull -PathType Container)) {
        throw "Snapshot source directory not found: $sourceFull"
    }
    if (Test-Path -LiteralPath $destinationFull) {
        throw "Snapshot already exists; refusing to overwrite: $destinationFull"
    }

    # Preflight the whole payload before creating a snapshot. Never silently skip links.
    $entries = [System.Collections.Generic.List[object]]::new()
    $queue = [System.Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($sourceFull)
    $excluded = 0
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        foreach ($item in @(Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop)) {
            if ($item.Name -ieq '.git') { $excluded++; continue }
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
    param([string]$Root, [switch]$ExcludeGit)
    Assert-RecoveryPlainPath $Root
    $nativeRoot = ConvertTo-SnapshotExtendedPath $Root
    if (-not [IO.Directory]::Exists($nativeRoot)) { throw 'Recovery tree is missing.' }
    $manifest = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    $queue = [Collections.Generic.Queue[string]]::new()
    $queue.Enqueue($nativeRoot)
    while ($queue.Count -gt 0) {
        $directory = $queue.Dequeue()
        foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($directory)) {
            if ([IO.Path]::GetFileName($entry) -ieq '.git') {
                if ($ExcludeGit) { continue }
                throw 'Pending snapshot unexpectedly contains Git metadata.'
            }
            $attributes = [IO.File]::GetAttributes($entry)
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
        [Parameter(Mandatory=$true)][string]$Destination
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
    $sourceBefore = Get-RecoverySnapshotManifest -Root $Source -ExcludeGit
    $pendingManifest = Get-RecoverySnapshotManifest -Root $Pending
    Assert-RecoveryManifestEqual $sourceBefore $pendingManifest
    # Catch changes during the full hash pass. Callers must keep source writers quiescent.
    $sourceAfter = Get-RecoverySnapshotManifest -Root $Source -ExcludeGit
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
