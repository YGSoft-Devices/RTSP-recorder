# Script de déploiement complet pour 192.168.1.4
param(
    [string]$IP = "192.168.1.4"
)

$files = @(
    @{ Source = "web-manager/blueprints/camera_bp.py"; Dest = "/opt/rpi-cam-webmanager/blueprints/" },
    @{ Source = "web-manager/blueprints/recordings_bp.py"; Dest = "/opt/rpi-cam-webmanager/blueprints/" },
    @{ Source = "web-manager/services/system_service.py"; Dest = "/opt/rpi-cam-webmanager/services/" },
    @{ Source = "web-manager/static/js/app.js"; Dest = "/opt/rpi-cam-webmanager/static/js/" }
)

Write-Host "Déploiement vers $IP" -ForegroundColor Cyan

foreach ($file in $files) {
    Write-Host "Transférant $($file.Source)..." -ForegroundColor Yellow
    .\debug_tools\deploy_scp.ps1 -Source $file.Source -Dest $file.Dest -IpEthernet $IP -NoRestart
}

Write-Host "Redémarrage du service..." -ForegroundColor Cyan
.\debug_tools\run_remote.ps1 -IP $IP "sudo systemctl restart rpi-cam-webmanager && sleep 3 && echo 'Redémarrage OK'"

Write-Host "Vérification du statut..." -ForegroundColor Cyan
.\debug_tools\run_remote.ps1 -IP $IP "sudo systemctl is-active rpi-cam-webmanager && echo 'Service Active'"

Write-Host "Déploiement terminé!" -ForegroundColor Green
