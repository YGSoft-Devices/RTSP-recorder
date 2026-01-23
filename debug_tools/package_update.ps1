# Version: 1.0.1
param(
    [string]$OutputDir = ".\\dist\\updates",
    [string]$OverrideVersion = "",
    [string[]]$RequiredPackages = @(),
    [switch]$RequiresReboot
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$versionPath = Join-Path $repoRoot "VERSION"
$version = (Get-Content -Path $versionPath -ErrorAction Stop).Trim()
if ($OverrideVersion) {
    $version = $OverrideVersion
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputName = "rpi-cam-update_${version}_${timestamp}.tar.gz"
$outputDirPath = Resolve-Path -Path $OutputDir -ErrorAction SilentlyContinue

if (-not $outputDirPath) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $outputDirPath = Resolve-Path -Path $OutputDir
}

if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
    throw "tar command not found. Install Windows tar or use WSL."
}

$staging = Join-Path $env:TEMP "rpi-cam-update-$timestamp"
$payloadRoot = Join-Path $staging "payload"

New-Item -ItemType Directory -Force -Path $payloadRoot | Out-Null

$destWebManager = Join-Path $payloadRoot "opt\\rpi-cam-webmanager"
$destOnvif = Join-Path $destWebManager "onvif-server"
$destBin = Join-Path $payloadRoot "usr\\local\\bin"

New-Item -ItemType Directory -Force -Path $destWebManager | Out-Null
New-Item -ItemType Directory -Force -Path $destOnvif | Out-Null
New-Item -ItemType Directory -Force -Path $destBin | Out-Null

Copy-Item -Recurse -Force (Join-Path $repoRoot "web-manager\\*") $destWebManager
Copy-Item -Recurse -Force (Join-Path $repoRoot "onvif-server\\*") $destOnvif
Copy-Item -Force (Join-Path $repoRoot "VERSION") (Join-Path $destWebManager "VERSION")

$binFiles = @(
    "rpi_av_rtsp_recorder.sh",
    "rtsp_recorder.sh",
    "rtsp_watchdog.sh",
    "rpi_csi_rtsp_server.py"
)

foreach ($file in $binFiles) {
    $src = Join-Path $repoRoot $file
    if (-not (Test-Path $src)) {
        throw "Missing file: $file"
    }
    Copy-Item -Force $src $destBin
}

$files = Get-ChildItem -Path $payloadRoot -Recurse -File
$manifestFiles = @()

foreach ($file in $files) {
    $relative = $file.FullName.Substring($payloadRoot.Length + 1).Replace("\\", "/")
    $hash = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash.ToLower()
    $manifestFiles += [ordered]@{
        path = $relative
        size = $file.Length
        sha256 = $hash
    }
}

$manifest = [ordered]@{
    schema_version = 1
    version = $version
    created_at = (Get-Date -Format "s")
    requires_reboot = [bool]$RequiresReboot
    required_packages = $RequiredPackages
    restart_services = @(
        "rpi-av-rtsp-recorder",
        "rpi-cam-onvif",
        "rpi-cam-webmanager"
    )
    files = $manifestFiles
}

$manifestPath = Join-Path $staging "update_manifest.json"
$manifestJson = $manifest | ConvertTo-Json -Depth 6
Set-Content -Path $manifestPath -Value $manifestJson -Encoding ascii

$outputPath = Join-Path $outputDirPath $outputName
Push-Location $staging
try {
    & tar -czf $outputPath update_manifest.json payload
} finally {
    Pop-Location
    Remove-Item -Recurse -Force $staging
}

Write-Host "Update package created: $outputPath"
