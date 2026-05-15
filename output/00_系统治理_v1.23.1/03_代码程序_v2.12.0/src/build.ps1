<#
.SYNOPSIS
    Build init_workspace.py + templates into single-file EXE.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ".\build.ps1"
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Version = "2.12.0"
$ExeName = "init_workspace_v$Version"
Write-Host ""
Write-Host "=========================================="
Write-Host "  Build: $ExeName.exe"
Write-Host "=========================================="
$pyVersion = python --version 2>&1
Write-Host "  Python : $pyVersion"
$piCheck = python -m pip show pyinstaller 2>$null
if ($LASTEXITCODE -ne 0) { python -m pip install pyinstaller }
Write-Host "  Building EXE ...`n"
$srcDir = $PSScriptRoot
$templatesAbs = Join-Path $srcDir "templates"
$distAbs = Join-Path (Split-Path $srcDir -Parent) "dist"
$buildTmpAbs = Join-Path (Split-Path $srcDir -Parent) "build_tmp"
$scriptAbs = Join-Path $srcDir "init_workspace.py"
$exePath = Join-Path $distAbs "$ExeName.exe"
if (Test-Path $buildTmpAbs) { Remove-Item -LiteralPath $buildTmpAbs -Recurse -Force }
if (Test-Path $distAbs) {
    Get-ChildItem -LiteralPath $distAbs -Filter "*.exe" -File |
        Where-Object { $_.Name -match '^(init_workspace|初始化工作区)_v\d+\.\d+\.\d+\.exe$' } |
        Remove-Item -Force
}
python -m PyInstaller --clean --onefile --noconsole --add-data "$templatesAbs;templates" --name $ExeName --distpath $distAbs --workpath $buildTmpAbs --specpath $buildTmpAbs $scriptAbs
Write-Host ""
if (Test-Path $exePath) { $sizeMB = [math]::Round((Get-Item $exePath).Length / 1MB, 1); Write-Host "==========================================`n  Build Successful`n  EXE  : $exePath`n  Size : $sizeMB MB`n==========================================" } else { Write-Host "==========================================`n  Build Failed`n==========================================" }
