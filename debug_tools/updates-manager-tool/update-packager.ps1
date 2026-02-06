<#
.SYNOPSIS
    Creates an update package for updates-manager-tool.

.DESCRIPTION
    This script packages the updates-manager-tool application into a ZIP file
    suitable for distribution via the Meeting update server.
    
    Excludes:
    - .venv/ (virtual environment)
    - dist/ (output directory)
    - __pycache__/ (Python cache)
    - *.pyc (compiled Python files)
    - .git/ (git repository)
    - *.log (log files)
    - .env (environment files)

.PARAMETER Version
    Version number for the package (e.g., "1.1.0"). If not provided, reads from app/version.py

.PARAMETER OutputDir
    Output directory for the package. Default: ./dist

.EXAMPLE
    .\update-packager.ps1
    Creates a package with version from app/version.py

.EXAMPLE
    .\update-packager.ps1 -Version "1.2.0"
    Creates a package with version 1.2.0
#>

param(
    [string]$Version = "",
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Updates Manager Tool - Packager" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Read version from app/version.py if not provided
if (-not $Version) {
    $versionFile = Join-Path $ScriptDir "app\version.py"
    if (Test-Path $versionFile) {
        $content = Get-Content $versionFile -Raw
        if ($content -match '__version__\s*=\s*"([^"]+)"') {
            $Version = $Matches[1]
            Write-Host "Read version from app/version.py: $Version" -ForegroundColor Green
        } elseif ($content -match "__version__\s*=\s*'([^']+)'") {
            $Version = $Matches[1]
            Write-Host "Read version from app/version.py: $Version" -ForegroundColor Green
        } else {
            Write-Host "Could not parse version from app/version.py" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "app/version.py not found, please specify -Version" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Package version: $Version" -ForegroundColor Yellow
Write-Host ""

# Create output directory
$distPath = Join-Path $ScriptDir $OutputDir
if (-not (Test-Path $distPath)) {
    New-Item -ItemType Directory -Path $distPath -Force | Out-Null
    Write-Host "Created output directory: $distPath" -ForegroundColor Green
}

# Package filename
$packageName = "updates-manager-tool-v$Version.zip"
$packagePath = Join-Path $distPath $packageName

# Remove existing package if exists
if (Test-Path $packagePath) {
    Remove-Item $packagePath -Force
    Write-Host "Removed existing package: $packageName" -ForegroundColor Yellow
}

# Create temporary directory for staging
$tempDir = Join-Path $env:TEMP "umt-package-$(Get-Random)"
$stagingDir = Join-Path $tempDir "updates-manager-tool"
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

Write-Host "Staging directory: $tempDir" -ForegroundColor Gray
Write-Host ""

# Files and directories to exclude
$excludePatterns = @(
    ".venv",
    "dist",
    "__pycache__",
    ".git",
    ".gitignore",
    "*.pyc",
    "*.pyo",
    "*.log",
    ".env",
    ".env.*",
    "*.egg-info",
    ".pytest_cache",
    ".mypy_cache",
    ".coverage",
    "htmlcov",
    "*.spec",
    "build"
)

Write-Host "Copying files..." -ForegroundColor Cyan

# Get all files, excluding patterns
$files = Get-ChildItem -Path $ScriptDir -Recurse -File | Where-Object {
    $relativePath = $_.FullName.Substring($ScriptDir.Length + 1)
    $include = $true
    
    foreach ($pattern in $excludePatterns) {
        # Check if path contains excluded directory
        if ($relativePath -like "*$pattern*" -or $relativePath -like "$pattern\*" -or $relativePath -like "*\$pattern\*") {
            $include = $false
            break
        }
        # Check file pattern
        if ($_.Name -like $pattern) {
            $include = $false
            break
        }
    }
    
    # Additional check for .venv specifically (case-insensitive)
    if ($relativePath -match "^\.venv" -or $relativePath -match "[\\/]\.venv") {
        $include = $false
    }
    
    # Additional check for dist specifically
    if ($relativePath -match "^dist" -or $relativePath -match "[\\/]dist") {
        $include = $false
    }
    
    $include
}

$fileCount = 0
foreach ($file in $files) {
    $relativePath = $file.FullName.Substring($ScriptDir.Length + 1)
    $destPath = Join-Path $stagingDir $relativePath
    $destDir = Split-Path -Parent $destPath
    
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    
    Copy-Item $file.FullName -Destination $destPath -Force
    $fileCount++
}

Write-Host "Copied $fileCount files" -ForegroundColor Green
Write-Host ""

# Create the ZIP package
Write-Host "Creating ZIP package..." -ForegroundColor Cyan
Compress-Archive -Path $stagingDir -DestinationPath $packagePath -CompressionLevel Optimal

# Calculate SHA256
$hash = Get-FileHash -Path $packagePath -Algorithm SHA256
$sha256 = $hash.Hash.ToLower()

# Get file size
$fileSize = (Get-Item $packagePath).Length
$fileSizeMB = [math]::Round($fileSize / 1MB, 2)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Package created successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Package: $packagePath" -ForegroundColor White
Write-Host "Size: $fileSizeMB MB ($fileSize bytes)" -ForegroundColor White
Write-Host "SHA256: $sha256" -ForegroundColor White
Write-Host ""

# Create metadata file
$metadataPath = Join-Path $distPath "updates-manager-tool-v$Version.json"
$metadata = @{
    version = $Version
    filename = $packageName
    sha256 = $sha256
    file_size = $fileSize
    created = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    device_type = "updates-manager-tool"
} | ConvertTo-Json -Depth 2

$metadata | Out-File -FilePath $metadataPath -Encoding UTF8
Write-Host "Metadata: $metadataPath" -ForegroundColor White

# Cleanup temp directory
Remove-Item -Path $tempDir -Recurse -Force
Write-Host ""
Write-Host "Temporary files cleaned up." -ForegroundColor Gray

Write-Host ""
Write-Host "To publish this update, use:" -ForegroundColor Yellow
Write-Host "  .\Run-CLI.ps1 publish `"$packagePath`" --device-type updates-manager-tool --version $Version --distribution stable" -ForegroundColor Cyan
Write-Host ""
