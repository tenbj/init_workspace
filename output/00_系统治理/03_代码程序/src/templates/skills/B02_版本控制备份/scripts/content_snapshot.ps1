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
