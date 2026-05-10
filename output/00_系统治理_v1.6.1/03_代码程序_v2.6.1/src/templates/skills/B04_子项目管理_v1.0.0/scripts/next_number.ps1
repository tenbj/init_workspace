<#
.SYNOPSIS
    Get the next file number for a sub-project sub-folder.
.DESCRIPTION
    Scans a sub-folder inside a sub-project directory for content files matching
    the pattern {NN}_{title}.ext and returns the next available number.
    Internal files do not carry version suffixes; the sub-folder carries the
    category version instead.
    Skips fixed files: 目录.md, 版本记录.md.
    Each of the three sub-folders (01_问题答疑, 02_课题研究, 03_代码程序)
    maintains its own independent numbering starting from 01.
.PARAMETER ProjectPath
    Path to the sub-project directory (e.g. output\06_睡眠优化_v1.0.0).
.PARAMETER SubFolder
    Name of the sub-folder to scan. One of:
      01_问题答疑_v*  /  02_课题研究_v*  /  03_代码程序_v*
    If omitted, scans the sub-folder whose name starts with the given prefix.
    Accepts short form: "01", "02", "03" or full name.
.EXAMPLE
    .\next_number.ps1 -ProjectPath "output\06_睡眠优化_v1.0.0" -SubFolder "02"
    # Returns: 01  (if no content files exist in 02_课题研究_v* yet)
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectPath,

    [Parameter(Mandatory=$false)]
    [string]$SubFolder = ""
)

if (-not (Test-Path $ProjectPath)) {
    Write-Error "Project path not found: $ProjectPath"
    exit 1
}

$fixedFiles = @("目录.md", "版本记录.md")

# Resolve the target scan directory
$scanDir = $ProjectPath
if ($SubFolder -ne "") {
    # Try exact match first
    $exact = Join-Path $ProjectPath $SubFolder
    if (Test-Path $exact) {
        $scanDir = $exact
    } else {
        # Try prefix match (e.g. "01" matches "01_问题答疑_v0.0.0")
        $matched = Get-ChildItem -Path $ProjectPath -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "$SubFolder*" } |
            Select-Object -First 1
        if ($matched) {
            $scanDir = $matched.FullName
        } else {
            Write-Error "Sub-folder not found matching '$SubFolder' in $ProjectPath"
            exit 1
        }
    }
}

$existingNumbers = @(
    Get-ChildItem -Path $scanDir -File -ErrorAction SilentlyContinue |
        Where-Object { $fixedFiles -notcontains $_.Name } |
        ForEach-Object {
            if ($_.Name -match '^(\d{2})_') {
                [int]$matches[1]
            }
        }
) | Sort-Object -Descending

$nextNumber = if ($existingNumbers.Count -gt 0) {
    $existingNumbers[0] + 1
} else {
    1
}

"{0:D2}" -f $nextNumber
