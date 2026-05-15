param([string]$Path)
if (Test-Path $Path) {
    Remove-Item -Path $Path -Recurse -Force
    Write-Host "[OK] Removed: $Path"
} else {
    Write-Host "[SKIP] Not found: $Path"
}
