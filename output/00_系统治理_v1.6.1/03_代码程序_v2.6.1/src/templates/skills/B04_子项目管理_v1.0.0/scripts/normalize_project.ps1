<#
.SYNOPSIS
    Migrate an existing sub-project to the new structure.
.DESCRIPTION
    1. Renames content files with {NN}_ prefix (sorted by creation time)
    2. Generates catalog.md
    3. Appends normalization entry to version-log.md
.PARAMETER ProjectPath
    Path to the sub-project directory.
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectPath,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

function Get-Chinese($bytes) {
    return [System.Text.Encoding]::UTF8.GetString($bytes)
}

$S_catalog       = Get-Chinese (@(0xE7,0x9B,0xAE,0xE5,0xBD,0x95))
$S_versionLog    = Get-Chinese (@(0xE7,0x89,0x88,0xE6,0x9C,0xAC,0xE8,0xAE,0xB0,0xE5,0xBD,0x95))
$S_dot           = Get-Chinese (@(0xC2,0xB7))
$S_subDesc       = Get-Chinese (@(0xE6,0x9C,0xAC,0xE5,0xAD,0x90,0xE9,0xA1,0xB9,0xE7,0x9B,0xAE,0xE5,0x86,0x85,0xE6,0x89,0x80,0xE6,0x9C,0x89,0xE5,0x86,0x85,0xE5,0xAE,0xB9,0xE6,0x96,0x87,0xE4,0xBB,0xB6,0xE7,0x9A,0x84,0xE7,0xB4,0xA2,0xE5,0xBC,0x95,0xE3,0x80,0x82))
$S_file          = Get-Chinese (@(0xE6,0x96,0x87,0xE4,0xBB,0xB6))
$S_desc          = Get-Chinese (@(0xE8,0xAF,0xB4,0xE6,0x98,0x8E))
$S_first         = Get-Chinese (@(0xE9,0xA6,0x96,0xE6,0xAC,0xA1,0xE8,0x90,0xBD,0xE7,0x9B,0x98))
$S_last          = Get-Chinese (@(0xE6,0x9C,0x80,0xE8,0xBF,0x91,0xE6,0x9B,0xB4,0xE6,0x96,0xB0))
$S_normalize     = Get-Chinese (@(0xE8,0xA7,0x84,0xE8,0x8C,0x83,0xE5,0x8C,0x96))
$S_normalized      = Get-Chinese (@(0xE5,0xB7,0xB2,0xE8,0xA7,0x84,0xE8,0x8C,0x83,0xE5,0x8C,0x96))
$S_initCatalog   = Get-Chinese (@(0xE5,0x88,0x9D,0xE5,0xA7,0x8B,0xE5,0x8C,0x96,0xE7,0x9B,0xAE,0xE5,0xBD,0x95))

if (-not (Test-Path $ProjectPath)) {
    Write-Error "Project path not found: $ProjectPath"
    exit 1
}

$catalogFile = "$S_catalog.md"
$versionFile = "$S_versionLog.md"
$fixedFiles = @($catalogFile, $versionFile)

$topic = Split-Path $ProjectPath -Leaf
if ($topic -match '^\d+_(.+?)_v\d+') {
    $topic = $Matches[1]
}

$files = Get-ChildItem -Path $ProjectPath -File |
    Where-Object { $fixedFiles -notcontains $_.Name -and $_.Name -match '\.(md|html|txt|ps1)$' } |
    Sort-Object CreationTime

if ($files.Count -eq 0) {
    Write-Host "No content files found to normalize."
    exit 0
}

if ($DryRun) {
    Write-Host "=== DRY RUN ==="
    $n = 1
    foreach ($f in $files) {
        $newNum = "{0:D2}" -f $n
        $newName = "${newNum}_$($f.Name)"
        Write-Host "  $($f.Name) -> $newName  ($($f.CreationTime))"
        $n++
    }
    Write-Host "=== DRY RUN ==="
    exit 0
}

$displayTimestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$todayDate = Get-Date -Format "yyyy-MM-dd"
$utf8Bom = [System.Text.UTF8Encoding]::new($true)

$n = 1
$catalogRows = @()

foreach ($f in $files) {
    $newNum = "{0:D2}" -f $n
    $newName = "${newNum}_$($f.Name)"
    $newPath = Join-Path $ProjectPath $newName
    $createdDate = Get-Date $f.CreationTime -Format "yyyy-MM-dd"
    $modifiedDate = Get-Date $f.LastWriteTime -Format "yyyy-MM-dd"

    Move-Item -LiteralPath $f.FullName -Destination $newPath -Force
    Write-Host "[OK] $($f.Name) -> $newName"

    $catalogRows += "| $newNum | [$newName](./$newName) | | $createdDate | $modifiedDate |"
    $n++
}

# Generate catalog.md
$catalogContent = "# $S_catalog $S_dot $topic`r`n`r`n> $S_subDesc`r`n`r`n| # | $S_file | $S_desc | $S_first | $S_last |`r`n|---|------|------|---------|---------|`r`n"
$catalogContent += ($catalogRows -join "`r`n")
$catalogContent += "`r`n"
$catalogPath = Join-Path $ProjectPath $catalogFile
[System.IO.File]::WriteAllText($catalogPath, $catalogContent, $utf8Bom)
Write-Host "[OK] Generated: $catalogFile"

# Append normalization entry to version-log.md
$versionPath = Join-Path $ProjectPath $versionFile
if (Test-Path $versionPath) {
    $vc = [System.IO.File]::ReadAllText($versionPath)
} else {
    $vc = "# $S_versionLog $S_dot $topic`r`n`r`n> $S_normalized`r`n`r`n---`r`n`r`n"
}

$entry = "`r`n## $S_normalize ($displayTimestamp)`r`n`r`n"
$entry += "**$S_desc**: $S_initCatalog ($displayTimestamp)`r`n`r`n"
$entry += "| $S_file | $S_desc |`r`n"
$entry += "|------|---------|`r`n"
$n2 = 1
foreach ($f in $files) {
    $newNum = "{0:D2}" -f $n2
    $newName = "${newNum}_$($f.Name)"
    $entry += "| $newName | $S_normalized |`r`n"
    $n2++
}
$entry += "`r`n---`r`n"

$insertPos = $vc.IndexOf("---") + 3
if ($insertPos -gt 2) {
    $vc = $vc.Insert($insertPos, $entry)
} else {
    $vc += $entry
}
[System.IO.File]::WriteAllText($versionPath, $vc, $utf8Bom)
Write-Host "[OK] Updated: $versionFile"

Write-Host ""
Write-Host "=========================================="
Write-Host "  Migration Complete"
Write-Host "=========================================="
Write-Host "  Project : $topic"
Write-Host "  Files   : $($files.Count)"
Write-Host "  Path    : $ProjectPath"
Write-Host "=========================================="
