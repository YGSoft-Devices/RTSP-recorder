# ssh_device.ps1 - Connexion SSH au device sans mot de passe interactif
# Version: 1.0.1
#
# Utilise plink (PuTTY) ou ssh avec sshpass pour éviter la saisie manuelle du mot de passe
# 
# Usage:
#   .\ssh_device.ps1                    # Connexion interactive
#   .\ssh_device.ps1 -Command "cmd"     # Exécuter une commande
#   .\ssh_device.ps1 -UseWifi           # Utiliser l'IP WiFi

param(
    [string]$Command = "",
    [switch]$UseWifi,
    [string]$User = "device",
    [string]$Password = "meeting",
    [string]$IpEthernet = "192.168.1.202",
    [string]$IpWifi = "192.168.1.124"
)

# Sélection de l'IP
$DeviceIP = if ($UseWifi) { $IpWifi } else { $IpEthernet }

Write-Host "=== SSH Device Connection ===" -ForegroundColor Cyan
Write-Host "Target: $User@$DeviceIP" -ForegroundColor Gray

# Options SSH communes pour éviter les prompts
$SshOptions = @(
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR"
)

# Vérifier si sshpass est disponible (WSL ou installé)
$UseSshpass = $false
$SshpassPath = $null

# Chercher sshpass dans WSL
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    $WslCheck = wsl which sshpass 2>$null
    if ($WslCheck) {
        $UseSshpass = $true
        $SshpassPath = "wsl"
    }
}

# Fonction pour exécuter via WSL+sshpass
function Invoke-SshpassCommand {
    param([string]$Cmd)
    
    if ($Cmd) {
        # Commande unique
        $WslCmd = "sshpass -p '$Password' ssh $($SshOptions -join ' ') $User@$DeviceIP `"$Cmd`""
        wsl bash -c $WslCmd
    } else {
        # Session interactive
        Write-Host "Connexion interactive via WSL+sshpass..." -ForegroundColor Yellow
        $WslCmd = "sshpass -p '$Password' ssh $($SshOptions -join ' ') $User@$DeviceIP"
        wsl bash -c $WslCmd
    }
}

# Fonction pour exécuter via SSH natif Windows (nécessite clé SSH ou entrée manuelle)
function Invoke-NativeSsh {
    param([string]$Cmd)
    
    # Construire la variable d'environnement pour le mot de passe
    $env:SSHPASS = $Password
    
    if ($Cmd) {
        # Commande unique - utiliser echo du mot de passe via stdin
        Write-Host "Exécution: $Cmd" -ForegroundColor Yellow
        
        # Essayer avec l'authentification par clé d'abord, sinon mot de passe
        $SshArgs = $SshOptions + @("$User@$DeviceIP", $Cmd)
        
        # Utiliser Start-Process pour capturer la sortie
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = "ssh"
        $pinfo.RedirectStandardInput = $true
        $pinfo.RedirectStandardOutput = $true
        $pinfo.RedirectStandardError = $true
        $pinfo.UseShellExecute = $false
        $pinfo.Arguments = ($SshOptions + @("$User@$DeviceIP", $Cmd)) -join " "
        
        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $pinfo
        $p.Start() | Out-Null
        
        # Envoyer le mot de passe si demandé
        Start-Sleep -Milliseconds 500
        $p.StandardInput.WriteLine($Password)
        
        $stdout = $p.StandardOutput.ReadToEnd()
        $stderr = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        
        if ($stdout) { Write-Host $stdout }
        if ($stderr -and $stderr -notmatch "Warning|Permanently added") { 
            Write-Host $stderr -ForegroundColor Red 
        }
        
        return $p.ExitCode
    } else {
        # Session interactive
        Write-Host "Connexion interactive (mot de passe: $Password)..." -ForegroundColor Yellow
        Write-Host "Tip: Configurez une clé SSH pour éviter la saisie du mot de passe" -ForegroundColor Gray
        & ssh @SshOptions "$User@$DeviceIP"
    }
}

# Exécution principale
if ($UseSshpass) {
    Write-Host "Mode: WSL + sshpass (automatique)" -ForegroundColor Green
    Invoke-SshpassCommand -Cmd $Command
} else {
    Write-Host "Mode: SSH natif Windows" -ForegroundColor Yellow
    Write-Host "Note: Installez sshpass dans WSL pour une connexion sans mot de passe" -ForegroundColor Gray
    Write-Host "      wsl sudo apt install sshpass" -ForegroundColor Gray
    Write-Host ""
    Invoke-NativeSsh -Cmd $Command
}
