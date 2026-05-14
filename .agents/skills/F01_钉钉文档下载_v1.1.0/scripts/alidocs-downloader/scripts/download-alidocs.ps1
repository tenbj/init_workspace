[CmdletBinding()]
param(
    [string]$Doc = "",
    [string]$Config = "",
    [string]$Output,
    [string]$ProfileDir,
    [string]$DownloadDir,
    [int]$Port = 0,
    [switch]$NoLaunch,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$node = Get-Command node -ErrorAction Stop
$script = Join-Path $PSScriptRoot "download-alidocs.mjs"
$defaultConfig = Join-Path $PSScriptRoot "..\config\docs.json"
if (-not $Config) {
    $Config = $defaultConfig
}
$resolvedConfig = (Resolve-Path -LiteralPath $Config).Path

$nodeArgs = @(
    $script,
    "--config", $resolvedConfig
)

if ($Help) {
    $nodeArgs += "--help"
}

if ($Doc) {
    $nodeArgs += @("--doc", $Doc)
}

if ($Output) {
    $nodeArgs += @("--output", $Output)
}

if ($ProfileDir) {
    $nodeArgs += @("--profile-dir", $ProfileDir)
}

if ($DownloadDir) {
    $nodeArgs += @("--download-dir", $DownloadDir)
}

if ($Port -gt 0) {
    $nodeArgs += @("--port", "$Port")
}

if ($NoLaunch) {
    $nodeArgs += "--no-launch"
}

& $node.Source @nodeArgs
exit $LASTEXITCODE
