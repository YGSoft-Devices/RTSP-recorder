# Get-DeviceIP.ps1 - Récupérer l'IP du device depuis l'API Meeting
# Version: 1.1.0
#
# Ce script interroge l'API Meeting pour obtenir l'IP actuelle du device.
# Il utilise le fichier de configuration local ou les variables d'environnement.
#
# Usage:
#   . .\Get-DeviceIP.ps1
#   $ip = Get-DeviceIPFromMeeting
#   $ip = Get-DeviceIPFromMeeting -FallbackIP "192.168.1.202"
#
# Configuration (dans debug_tools/meeting_config.json ou variables d'env):
#   MEETING_API_URL, MEETING_DEVICE_KEY, MEETING_TOKEN_CODE

param()

$script:MeetingConfigFile = Join-Path $PSScriptRoot "meeting_config.json"

function Get-MeetingConfig {
    <#
    .SYNOPSIS
    Charge la configuration Meeting depuis le fichier local ou les variables d'environnement.
    #>
    param(
        [string]$ConfigFile
    )
    
    $config = @{
        ApiUrl = $env:MEETING_API_URL
        DeviceKey = $env:MEETING_DEVICE_KEY
        TokenCode = $env:MEETING_TOKEN_CODE
    }

    $configFileToUse = if ($ConfigFile) { $ConfigFile } else { $script:MeetingConfigFile }
    
    # Essayer de charger depuis le fichier JSON
    if (Test-Path $configFileToUse) {
        try {
            $fileConfig = Get-Content $configFileToUse -Raw | ConvertFrom-Json
            if ($fileConfig.api_url) { $config.ApiUrl = $fileConfig.api_url }
            if ($fileConfig.device_key) { $config.DeviceKey = $fileConfig.device_key }
            if ($fileConfig.token_code) { $config.TokenCode = $fileConfig.token_code }
        } catch {
            Write-Verbose "Impossible de lire $configFileToUse : $_"
        }
    }
    
    return $config
}

function Set-MeetingConfig {
    <#
    .SYNOPSIS
    Sauvegarde la configuration Meeting dans le fichier local.
    #>
    param(
        [string]$ApiUrl,
        [string]$DeviceKey,
        [string]$TokenCode
    )
    
    $config = @{
        api_url = $ApiUrl
        device_key = $DeviceKey
        token_code = $TokenCode
    }
    
    $config | ConvertTo-Json | Set-Content $script:MeetingConfigFile -Encoding UTF8
    Write-Host "Configuration Meeting sauvegardée dans $script:MeetingConfigFile" -ForegroundColor Green
}

function Get-DeviceIPFromMeeting {
    <#
    .SYNOPSIS
    Récupère l'IP du device depuis l'API Meeting.
    
    .PARAMETER FallbackIP
    IP à utiliser si l'API Meeting n'est pas accessible.
    
    .PARAMETER Timeout
    Timeout en secondes pour l'appel API.
    
    .OUTPUTS
    String - L'IP du device ou $null si non disponible.
    #>
    param(
        [string]$FallbackIP = "192.168.1.202",
        [int]$Timeout = 5,
        [switch]$Quiet,
        [string]$ApiUrl,
        [string]$DeviceKey,
        [string]$TokenCode,
        [string]$ConfigFile
    )
    
    $config = Get-MeetingConfig -ConfigFile $ConfigFile
    if ($ApiUrl) { $config.ApiUrl = $ApiUrl }
    if ($DeviceKey) { $config.DeviceKey = $DeviceKey }
    if ($TokenCode) { $config.TokenCode = $TokenCode }
    
    # Vérifier que la config est complète
    if (-not $config.ApiUrl -or -not $config.DeviceKey -or -not $config.TokenCode) {
        if (-not $Quiet) {
            Write-Host "[Meeting] Configuration incomplète, utilisation de l'IP par défaut" -ForegroundColor Yellow
        }
        return $FallbackIP
    }
    
    $url = "$($config.ApiUrl.TrimEnd('/'))/devices/$($config.DeviceKey)"
    
    try {
        if (-not $Quiet) {
            Write-Host "[Meeting] Récupération de l'IP depuis $($config.ApiUrl)..." -ForegroundColor Cyan
        }
        
        $headers = @{
            "X-Token-Code" = $config.TokenCode
            "Accept" = "application/json"
        }
        
        $response = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec $Timeout -ErrorAction Stop
        
        if ($response.ip_address) {
            if (-not $Quiet) {
                Write-Host "[Meeting] IP du device: $($response.ip_address)" -ForegroundColor Green
            }
            return $response.ip_address
        } else {
            if (-not $Quiet) {
                Write-Host "[Meeting] Pas d'IP dans la réponse, utilisation de l'IP par défaut" -ForegroundColor Yellow
            }
            return $FallbackIP
        }
    } catch {
        if (-not $Quiet) {
            Write-Host "[Meeting] Erreur API: $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "[Meeting] Utilisation de l'IP par défaut: $FallbackIP" -ForegroundColor Yellow
        }
        return $FallbackIP
    }
}

function Test-DeviceConnection {
    <#
    .SYNOPSIS
    Teste la connectivité vers le device.
    #>
    param(
        [Parameter(Mandatory=$true)]
        [string]$IP,
        [int]$Port = 22,
        [int]$Timeout = 2
    )
    
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $result = $tcpClient.BeginConnect($IP, $Port, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne($Timeout * 1000, $false)
        $tcpClient.Close()
        return $success
    } catch {
        return $false
    }
}

function Find-DeviceIP {
    <#
    .SYNOPSIS
    Trouve l'IP du device en essayant Meeting API puis les IPs connues.
    
    .DESCRIPTION
    Ordre de recherche:
    1. API Meeting (si configuré)
    2. IP Ethernet par défaut (192.168.1.202)
    3. IPs WiFi connues (192.168.1.124, 192.168.1.127)
    
    .OUTPUTS
    String - L'IP accessible du device ou $null.
    #>
    param(
        [switch]$Quiet,
        [string]$ApiUrl,
        [string]$DeviceKey,
        [string]$TokenCode,
        [string]$ConfigFile,
        [string[]]$KnownIPs
    )
    
    $knownIPs = if ($KnownIPs -and $KnownIPs.Count -gt 0) {
        $KnownIPs
    } else {
        @(
            "192.168.1.202",  # Ethernet
            "192.168.1.124",  # WiFi wlan1
            "192.168.1.127"   # WiFi wlan0
        )
    }
    
    # 1. Essayer l'API Meeting
    $meetingIP = Get-DeviceIPFromMeeting -Quiet:$Quiet -Timeout 3 -ApiUrl $ApiUrl -DeviceKey $DeviceKey -TokenCode $TokenCode -ConfigFile $ConfigFile
    if ($meetingIP -and (Test-DeviceConnection -IP $meetingIP -Timeout 2)) {
        if (-not $Quiet) {
            Write-Host "[Find] Device accessible via Meeting IP: $meetingIP" -ForegroundColor Green
        }
        return $meetingIP
    }
    
    # 2. Essayer les IPs connues
    foreach ($ip in $knownIPs) {
        if (-not $Quiet) {
            Write-Host "[Find] Test de $ip..." -ForegroundColor Gray -NoNewline
        }
        
        if (Test-DeviceConnection -IP $ip -Timeout 2) {
            if (-not $Quiet) {
                Write-Host " OK" -ForegroundColor Green
            }
            return $ip
        } else {
            if (-not $Quiet) {
                Write-Host " Pas de réponse" -ForegroundColor DarkGray
            }
        }
    }
    
    if (-not $Quiet) {
        Write-Host "[Find] Aucune IP accessible trouvée!" -ForegroundColor Red
    }
    return $null
}

# Note: Ce script est conçu pour être dot-sourcé (. .\Get-DeviceIP.ps1)
# Les fonctions sont automatiquement disponibles dans la session PowerShell
