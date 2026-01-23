#!/usr/bin/env pwsh
# Déploiement des modifications sur le device Raspberry Pi
# Version: 1.0.0

$ErrorActionPreference = "Stop"

# Configuration
$DEVICE_USER = "device"
$DEVICE_IP = "192.168.1.191"
$DEVICE_PASS = "meeting"
$REMOTE_WEBMANAGER = "/opt/rpi-cam-webmanager"
$REMOTE_SCRIPTS = "$REMOTE_WEBMANAGER/scripts"

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          DÉPLOIEMENT RTSP-Full - Energy Management         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Vérifier les fichiers locaux
Write-Host "📋 Vérification des fichiers..." -ForegroundColor Yellow
$files = @(
    @{ local = "web-manager/app.py"; remote = "$REMOTE_WEBMANAGER/" },
    @{ local = "web-manager/templates/index.html"; remote = "$REMOTE_WEBMANAGER/templates/" },
    @{ local = "web-manager/static/css/style.css"; remote = "$REMOTE_WEBMANAGER/static/css/" },
    @{ local = "web-manager/static/js/app.js"; remote = "$REMOTE_WEBMANAGER/static/js/" },
    @{ local = "scripts/energy_manager.sh"; remote = "$REMOTE_SCRIPTS/" }
)

$missing = 0
foreach ($file in $files) {
    if (Test-Path $file.local) {
        Write-Host "  ✓ $($file.local)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $($file.local) - NOT FOUND" -ForegroundColor Red
        $missing++
    }
}

if ($missing -gt 0) {
    Write-Host ""
    Write-Host "❌ Fichiers manquants. Arrêt du déploiement." -ForegroundColor Red
    exit 1
}

# Test de connectivité
Write-Host ""
Write-Host "🔗 Test de connectivité..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $DEVICE_IP -Count 1 -ErrorAction SilentlyContinue
if ($ping) {
    Write-Host "  ✓ Ping: ${$ping.ResponseTime}ms" -ForegroundColor Green
} else {
    Write-Host "  ✗ Impossible de pinger $DEVICE_IP" -ForegroundColor Red
    exit 1
}

# Copier les fichiers
Write-Host ""
Write-Host "📤 Déploiement des fichiers..." -ForegroundColor Yellow

$count = 0
foreach ($file in $files) {
    $count++
    $local_file = $file.local
    $remote_dir = $file.remote
    
    # Extraire le nom du fichier
    $filename = Split-Path $local_file -Leaf
    Write-Host "  [$count/5] $filename..." -NoNewline
    
    try {
        # Copie via SCP
        scp -q -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" `
            "$local_file" "$DEVICE_USER@$DEVICE_IP`:$remote_dir" 2>&1 | Out-Null
        
        Write-Host " ✓" -ForegroundColor Green
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        Write-Host "    Erreur: $_"
        exit 1
    }
}

# Tâches post-déploiement
Write-Host ""
Write-Host "⚙️  Tâches post-déploiement..." -ForegroundColor Yellow

# Rendre le script executable
Write-Host "  [1/3] Chmod energy_manager.sh..." -NoNewline
ssh -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" `
    "$DEVICE_USER@$DEVICE_IP" "chmod +x $REMOTE_SCRIPTS/energy_manager.sh" 2>&1 | Out-Null
Write-Host " ✓" -ForegroundColor Green

# Vérifier les versions
Write-Host "  [2/3] Vérification des versions..." -NoNewline
$version_check = ssh -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" `
    "$DEVICE_USER@$DEVICE_IP" "grep 'Version:' $REMOTE_WEBMANAGER/app.py | head -1" 2>&1
Write-Host " ✓" -ForegroundColor Green
Write-Host "    → $version_check"

# Redémarrer les services
Write-Host "  [3/3] Redémarrage du service web-manager..." -NoNewline
ssh -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" `
    "$DEVICE_USER@$DEVICE_IP" "sudo systemctl restart rpi-cam-webmanager" 2>&1 | Out-Null
Write-Host " ✓" -ForegroundColor Green

# Vérifier le service
Write-Host ""
Write-Host "✅ Vérification du service..." -ForegroundColor Yellow
$status = ssh -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" `
    "$DEVICE_USER@$DEVICE_IP" "sudo systemctl is-active rpi-cam-webmanager" 2>&1
if ($status -eq "active") {
    Write-Host "  ✓ Service rpi-cam-webmanager: ACTIF" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Service status: $status" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                   DÉPLOIEMENT RÉUSSI! 🎉                   ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Interface web: http://$DEVICE_IP:5000" -ForegroundColor Cyan
Write-Host "Fichiers déployés:" -ForegroundColor Cyan
foreach ($file in $files) {
    Write-Host "  • $($file.local) → $($file.remote)" -ForegroundColor Cyan
}
Write-Host ""
