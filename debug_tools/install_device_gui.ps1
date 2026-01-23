<#
 install_device_gui.ps1 - GUI wrapper for install_device.ps1 (Windows)
 Version: 1.4.0

 Objectif:
   - Compagnon grand public pour `install_device.ps1` (flash interactif du device)
   - Interface sombre, claire sur l'état d'avancement (barre + étapes)
   - Journalisation locale + suivi temps réel
   - Vérification post-install: heartbeat Meeting API + IP retournée
   - Sauvegarde et restauration des derniers paramètres utilisés

 Usage:
   .\debug_tools\install_device_gui.ps1

 Fonctionnalités:
   - Bouton "Restaurer" : récupère les derniers paramètres (install_gui_config.json)
   - Logs temps réel + persistence sur disque
   - Gestion propre des erreurs, event handlers robustes et thread-safe
   - Arguments CLI: -IP, -DeviceKey, -Token, -MeetingApiUrl, -Timezone, -User, -Password, -Launch

 Usage CLI (auto-launch):
   .\debug_tools\install_device_gui.ps1 -IP "192.168.1.202" -DeviceKey "3316A..." -Token "41e291" -Launch

 Notes:
   - Nécessite Windows + System.Windows.Forms (PowerShell 5.1 ou 7 sous Windows)
   - Exécute `install_device.ps1` dans un process séparé, capture stdout/stderr
   - Ne tente jamais de deviner l'IP via Meeting API: l'utilisateur saisit l'IP cible
#>

param(
    [string]$IP = "",
    [string]$DeviceKey = "",
    [string]$Token = "",
    [string]$MeetingApiUrl = "",
    [string]$Timezone = "Europe/Paris",
    [string]$User = "device",
    [string]$Password = "meeting",
    [switch]$Launch = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$script:autoLaunchAfterInit = $Launch

try {
    # Script initialization
    $scriptRoot = Split-Path -Parent $PSCommandPath

if ($env:OS -notlike "*Windows*") {
    throw "Ce script GUI est prévu pour Windows."
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# Thread-safe queue for log messages (producer-consumer pattern)
$script:logQueue = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
$script:uiTimer = $null

function Fail([string]$message) {
    [System.Windows.Forms.MessageBox]::Show(
        $message,
        "RTSP-Full - Install Device (GUI)",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

$configFilePath = Join-Path $scriptRoot "install_gui_config.json"

function Save-LastInstallConfig {
    param(
        [string]$ip,
        [string]$timezone,
        [string]$user,
        [string]$deviceKey,
        [string]$meetingApiUrl,
        [bool]$checkOnly,
        [bool]$skipInstall,
        [bool]$monitor,
        [bool]$noProvision,
        [bool]$noReboot,
        [bool]$noBurnToken
    )
    try {
        $config = @{
            ip = $ip
            timezone = $timezone
            user = $user
            deviceKey = $deviceKey
            meetingApiUrl = $meetingApiUrl
            checkOnly = $checkOnly
            skipInstall = $skipInstall
            monitor = $monitor
            noProvision = $noProvision
            noReboot = $noReboot
            noBurnToken = $noBurnToken
            timestamp = (Get-Date).ToString('o')
        }
        $config | ConvertTo-Json | Set-Content -LiteralPath $configFilePath -ErrorAction SilentlyContinue
    } catch { }
}

function Load-LastInstallConfig {
    try {
        if (Test-Path -LiteralPath $configFilePath) {
            return Get-Content -LiteralPath $configFilePath | ConvertFrom-Json
        }
    } catch { }
    return $null
}

$installerPath = Join-Path $scriptRoot "install_device.ps1"
if (-not (Test-Path -LiteralPath $installerPath)) {
    Fail "Installer introuvable: $installerPath"
}

# ---------------------------------------------------------------------------
# Thème & helpers
# ---------------------------------------------------------------------------
$theme = [ordered]@{
    Back        = [System.Drawing.Color]::FromArgb(18, 20, 28)
    Panel       = [System.Drawing.Color]::FromArgb(28, 32, 45)
    Accent      = [System.Drawing.Color]::FromArgb(94, 197, 255)
    Text        = [System.Drawing.Color]::FromArgb(235, 238, 245)
    SubText     = [System.Drawing.Color]::FromArgb(150, 156, 170)
    Danger      = [System.Drawing.Color]::FromArgb(255, 99, 99)
    Success     = [System.Drawing.Color]::FromArgb(120, 214, 120)
    Border      = [System.Drawing.Color]::FromArgb(55, 60, 75)
}

function Set-ThemeColors($control) {
    $control.BackColor = $theme.Back
    $control.ForeColor = $theme.Text
    foreach ($child in $control.Controls) {
        switch ($child.GetType().Name) {
            "GroupBox" { $child.BackColor = $theme.Panel; $child.ForeColor = $theme.Text }
            "Panel"    { $child.BackColor = $theme.Panel; $child.ForeColor = $theme.Text }
            "TableLayoutPanel" { $child.BackColor = $theme.Panel; $child.ForeColor = $theme.Text }
            "FlowLayoutPanel" { $child.BackColor = $theme.Panel; $child.ForeColor = $theme.Text }
            "TextBox"  { $child.BackColor = $theme.Back; $child.ForeColor = $theme.Text; $child.BorderStyle = "FixedSingle" }
            "ComboBox" { $child.BackColor = $theme.Back; $child.ForeColor = $theme.Text; $child.FlatStyle = "Flat" }
            "CheckBox" { $child.BackColor = $theme.Panel; $child.ForeColor = $theme.Text }
            "Button"   { $child.BackColor = $theme.Border; $child.ForeColor = $theme.Text; $child.FlatStyle = "Flat"; $child.FlatAppearance.BorderColor = $theme.Border }
            "NumericUpDown" { $child.BackColor = $theme.Back; $child.ForeColor = $theme.Text; $child.BorderStyle = "FixedSingle" }
            default     { }
        }
        Set-ThemeColors $child
    }
}

function Test-ContainsDoubleQuote([string]$value) {
    return ($null -ne $value -and $value.Contains('"'))
}

function Format-QuotedArg([string]$value) {
    if ($null -eq $value) { return '""' }
    if ($value -eq "") { return '""' }
    if ($value.StartsWith("-")) { return $value }
    return '"' + $value.Replace('"', '""') + '"'
}

function Build-InstallerArgs {
    [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingPlainTextForPassword','', Justification='install_device.ps1 requires plaintext password for sshpass and remote CLI compatibility.')]
    param(
        [string]$ip,
        [string]$timezone,
        [string]$user,
        [string]$password,
        [int]$timeoutSec,
        [string]$deviceKey,
        [string]$token,
        [string]$meetingApiUrl,
        [bool]$checkOnly,
        [bool]$skipInstall,
        [bool]$monitor,
        [bool]$noProvision,
        [bool]$noReboot,
        [bool]$noBurnToken
    )

    $stringInputs = @(
        @{ Name = "IP"; Value = $ip },
        @{ Name = "Timezone"; Value = $timezone },
        @{ Name = "User"; Value = $user },
        @{ Name = "Password"; Value = $password },
        @{ Name = "DeviceKey"; Value = $deviceKey },
        @{ Name = "Token"; Value = $token },
        @{ Name = "MeetingApiUrl"; Value = $meetingApiUrl }
    )
    foreach ($item in $stringInputs) {
        if (Test-ContainsDoubleQuote $item.Value) {
            Fail "Le champ '$($item.Name)' ne doit pas contenir de guillemets doubles."
        }
    }

    $builderArgs = [System.Collections.Generic.List[string]]::new()

    if ($ip) { [void]$builderArgs.Add("-IP"); [void]$builderArgs.Add($ip) }
    if ($checkOnly) { [void]$builderArgs.Add("-CheckOnly") }
    if ($skipInstall) { [void]$builderArgs.Add("-SkipInstall") }
    if ($monitor) { [void]$builderArgs.Add("-Monitor") }
    if ($noProvision) { [void]$builderArgs.Add("-NoProvision") }
    if ($noReboot) { [void]$builderArgs.Add("-NoReboot") }
    if ($noBurnToken) { [void]$builderArgs.Add("-NoBurnToken") }

    if ($timezone) { [void]$builderArgs.Add("-Timezone"); [void]$builderArgs.Add($timezone) }
    if ($user) { [void]$builderArgs.Add("-User"); [void]$builderArgs.Add($user) }
    if ($password) { [void]$builderArgs.Add("-Password"); [void]$builderArgs.Add($password) }
    if ($timeoutSec -gt 0) { [void]$builderArgs.Add("-Timeout"); [void]$builderArgs.Add([string]$timeoutSec) }

    if ($deviceKey) { [void]$builderArgs.Add("-DeviceKey"); [void]$builderArgs.Add($deviceKey) }
    if ($token) { [void]$builderArgs.Add("-Token"); [void]$builderArgs.Add($token) }
    if ($meetingApiUrl) { [void]$builderArgs.Add("-MeetingApiUrl"); [void]$builderArgs.Add($meetingApiUrl) }

    return $builderArgs.ToArray()
}

function Build-PowerShellArgumentString {
    param([string[]]$installerArgs)

    $parts = [System.Collections.Generic.List[string]]::new()
    [void]$parts.Add("-NoProfile")
    [void]$parts.Add("-ExecutionPolicy")
    [void]$parts.Add("Bypass")
    [void]$parts.Add("-File")
    [void]$parts.Add((Format-QuotedArg $installerPath))

    foreach ($a in $installerArgs) {
        [void]$parts.Add((Format-QuotedArg $a))
    }
    return ($parts -join " ")
}

function New-LogFilePath {
    param([string]$ip)
    $logsDir = Join-Path $scriptRoot "logs"
    if (-not (Test-Path $logsDir)) { [void](New-Item -ItemType Directory -Path $logsDir) }
    $stamp = (Get-Date).ToString('yyyyMMdd_HHmmss')
    $safeIp = if ($ip) { $ip.Replace(':', '_').Replace('/', '-') } else { 'unknown' }
        $logPath = Join-Path $logsDir "install_gui_${safeIp}_${stamp}.log"
    return $logPath
}

function Add-LogEntry {
    param(
        [System.Windows.Forms.TextBox]$textBox,
        [string]$text,
        [string]$logPath
    )
    try {
        $stamp = (Get-Date).ToString('HH:mm:ss')
        $line = "[$stamp] $text"

        # Write to file first (always works, thread-safe)
        if ($logPath) {
            try {
                Add-Content -LiteralPath $logPath -Value $line -ErrorAction SilentlyContinue
            } catch { }
        }

        # Enqueue for UI update (thread-safe, non-blocking)
        $script:logQueue.Enqueue($line)
    } catch { }
}

# Function called by Timer to dequeue and update UI safely
function Update-LogBoxFromQueue {
    param(
        [System.Windows.Forms.TextBox]$textBox
    )
    try {
        if ($null -eq $textBox -or $textBox.IsDisposed) { return }
        
        $item = $null
        $updated = $false
        
        # Dequeue all pending messages
        while ($script:logQueue.TryDequeue([ref]$item)) {
            if ($null -ne $item) {
                $textBox.AppendText($item + [Environment]::NewLine)
                $updated = $true
            }
        }
        
        # Scroll to end if updated
        if ($updated) {
            $textBox.SelectionStart = $textBox.TextLength
            $textBox.ScrollToCaret()
        }
    } catch { }
}

function Set-Stage {
    param(
        [System.Windows.Forms.ProgressBar]$progressBar,
        [System.Windows.Forms.Label]$label,
        [int]$percent,
        [string]$text
    )
    try {
        $p = [math]::Min(100, [math]::Max(0, $percent))
        
        # Ensure controls are valid before updating
        if ($progressBar -and -not $progressBar.IsDisposed) {
            try {
                if ($progressBar.InvokeRequired) {
                    $progressBar.Invoke([Action]{ $progressBar.Value = $p })
                } else {
                    $progressBar.Value = $p
                }
            } catch { }
        }
        
        if ($label -and -not $label.IsDisposed) {
            try {
                $labelText = "$p% — $text"
                if ($label.InvokeRequired) {
                    $label.Invoke([Action]{ $label.Text = $labelText })
                } else {
                    $label.Text = $labelText
                }
            } catch { }
        }
    } catch {
        # Silently ignore errors
    }
}

function Update-StageFromOutput {
    param(
        [string]$line,
        [System.Windows.Forms.ProgressBar]$progressBar,
        [System.Windows.Forms.Label]$label
    )

    try {
        # Use simple string matching instead of regex for performance
        if ($line -like "*Verification des prerequis*") { Set-Stage -progressBar $progressBar -label $label -percent 10 -text "Prérequis"; return }
        if ($line -like "*Test de connectivite*") { Set-Stage -progressBar $progressBar -label $label -percent 20 -text "Connexion SSH"; return }
        if ($line -like "*Provisionnement*") { Set-Stage -progressBar $progressBar -label $label -percent 35 -text "Provisionnement"; return }
        if ($line -like "*Configuration Meeting*") { Set-Stage -progressBar $progressBar -label $label -percent 45 -text "Meeting API"; return }
        if ($line -like "*Transfert des fichiers*") { Set-Stage -progressBar $progressBar -label $label -percent 55 -text "Transfert"; return }
        if ($line -like "*Installation sur le device*") { Set-Stage -progressBar $progressBar -label $label -percent 70 -text "Installation"; return }
        if ($line -like "*Detection de la camera*") { Set-Stage -progressBar $progressBar -label $label -percent 85 -text "Détection caméra"; return }
        if ($line -like "*INSTALLATION TERMINEE*") { Set-Stage -progressBar $progressBar -label $label -percent 95 -text "Terminé"; return }
        if ($line -like "*REDEMARRAGE AUTOMATIQUE*") { Set-Stage -progressBar $progressBar -label $label -percent 97 -text "Redémarrage"; return }
    } catch {
        # Silently ignore errors in stage update
    }
}

function Invoke-HeartbeatValidation {
    param(
        [string]$DeviceKey,
        [string]$Token,
        [string]$MeetingApiUrl,
        [string]$ExpectedIp,
        [int]$TimeoutSec = 120
    )

    if (-not $DeviceKey -or -not $Token) {
        return @{ Status = "skipped"; Message = "DeviceKey/Token absents" }
    }

    $headers = @{ "X-Token-Code" = $Token; "Accept" = "application/json" }
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastError = ""
    $lastInfo = $null
    $lastIp = ""

    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-RestMethod -Method POST -Uri "$MeetingApiUrl/devices/$DeviceKey/online" -Headers $headers -TimeoutSec 20 -ErrorAction Stop
        } catch {
            $lastError = $_.Exception.Message
        }

        try {
            $info = Invoke-RestMethod -Method GET -Uri "$MeetingApiUrl/devices/$DeviceKey" -Headers $headers -TimeoutSec 20 -ErrorAction Stop
            $lastInfo = $info
            $ipCandidates = @(
                $info.ip,
                $info.ip_address,
                $info.last_ip,
                $info.last_known_ip,
                $info.last_ip_address
            ) | Where-Object { $_ -and (-not ($_ -is [System.Management.Automation.PSObject])) }
            $reportedIp = $ipCandidates | Select-Object -First 1
            if ($reportedIp) { $lastIp = $reportedIp }

            $onlineFlags = @($info.online, $info.is_online, $info.state)
            $isOnline = $onlineFlags -contains $true -or $onlineFlags -contains "online"

            if ($isOnline -and ($ExpectedIp -eq "" -or $reportedIp -eq $ExpectedIp)) {
                return @{ Status = "ok"; ReportedIp = $reportedIp; Info = $info }
            }
        } catch {
            $lastError = $_.Exception.Message
        }

        Start-Sleep -Seconds 5
        [System.Windows.Forms.Application]::DoEvents()
    }

    return @{ Status = "timeout"; Message = $lastError; ReportedIp = $lastIp; Info = $lastInfo }
}

# ---------------------------------------------------------------------------
# UI construction
# ---------------------------------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "RTSP-Full — install_device.ps1 (GUI)"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(1100, 760)
$form.MinimumSize = New-Object System.Drawing.Size(1100, 760)
$form.BackColor = $theme.Back
$form.ForeColor = $theme.Text
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$rootLayout = New-Object System.Windows.Forms.TableLayoutPanel
$rootLayout.Dock = "Fill"
$rootLayout.ColumnCount = 2
$rootLayout.RowCount = 2
[void]$rootLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 42)))
[void]$rootLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 58)))
[void]$rootLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 48)))
[void]$rootLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$form.Controls.Add($rootLayout)

$header = New-Object System.Windows.Forms.Label
$header.Text = "RTSP-Full – Assistant d'installation (GUI) v1.1.0"
$header.AutoSize = $true
$header.Dock = "Fill"
$header.TextAlign = "MiddleLeft"
$header.Font = New-Object System.Drawing.Font("Segoe UI Semibold", 11)
$rootLayout.Controls.Add($header, 0, 0)
$rootLayout.SetColumnSpan($header, 2)

$leftPanel = New-Object System.Windows.Forms.Panel
$leftPanel.Dock = "Fill"
$leftPanel.AutoScroll = $true
$rootLayout.Controls.Add($leftPanel, 0, 1)

$rightPanel = New-Object System.Windows.Forms.Panel
$rightPanel.Dock = "Fill"
$rightPanel.AutoScroll = $true
$rootLayout.Controls.Add($rightPanel, 1, 1)

function New-GroupBoxControl([string]$title) {
    $gb = New-Object System.Windows.Forms.GroupBox
    $gb.Text = $title
    $gb.Dock = "Top"
    $gb.Padding = New-Object System.Windows.Forms.Padding(12)
    $gb.Margin = "0,0,0,12"
    return $gb
}

function New-GridLayout {
    $grid = New-Object System.Windows.Forms.TableLayoutPanel
    $grid.Dock = "Top"
    $grid.AutoSize = $true
    $grid.ColumnCount = 2
    $grid.RowCount = 1
    [void]$grid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 170)))
    [void]$grid.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    return $grid
}

function Add-RowText {
    param(
        [System.Windows.Forms.TableLayoutPanel]$grid,
        [string]$label,
        [System.Windows.Forms.Control]$control
    )
    $grid.RowCount++
    [void]$grid.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
    $row = $grid.RowCount - 1

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = $label
    $lbl.AutoSize = $true
    $lbl.TextAlign = "MiddleLeft"
    $lbl.Dock = "Fill"
    $lbl.Margin = "0,6,6,6"

    $control.Dock = "Top"
    $control.Margin = "0,3,0,3"
    $grid.Controls.Add($lbl, 0, $row)
    $grid.Controls.Add($control, 1, $row)
}

function New-CheckBoxControl([string]$text, [bool]$checked = $false) {
    $cb = New-Object System.Windows.Forms.CheckBox
    $cb.Text = $text
    $cb.AutoSize = $true
    $cb.Checked = $checked
    return $cb
}

# Configuration de base
$cfgGroup = New-GroupBoxControl "Configuration de base"
$cfgGroup.Height = 330
$leftPanel.Controls.Add($cfgGroup)

$cfgGrid = New-GridLayout
$cfgGroup.Controls.Add($cfgGrid)

$ipText = New-Object System.Windows.Forms.TextBox
Add-RowText -grid $cfgGrid -label "IP du device (obligatoire)" -control $ipText

$timezoneText = New-Object System.Windows.Forms.TextBox
$timezoneText.Text = "Europe/Paris"
Add-RowText -grid $cfgGrid -label "Timezone" -control $timezoneText

$userText = New-Object System.Windows.Forms.TextBox
$userText.Text = "device"
Add-RowText -grid $cfgGrid -label "User SSH" -control $userText

$passwordText = New-Object System.Windows.Forms.TextBox
$passwordText.Text = "meeting"
$passwordText.UseSystemPasswordChar = $true
Add-RowText -grid $cfgGrid -label "Password SSH" -control $passwordText

$timeoutNumeric = New-Object System.Windows.Forms.NumericUpDown
$timeoutNumeric.Minimum = 1
$timeoutNumeric.Maximum = 180
$timeoutNumeric.Value = 10
Add-RowText -grid $cfgGrid -label "Timeout SSH (s)" -control $timeoutNumeric

# Meeting API
$meetingGroup = New-GroupBoxControl "Meeting API (optionnel mais recommandé)"
$meetingGroup.Height = 240
$leftPanel.Controls.Add($meetingGroup)

$meetingGrid = New-GridLayout
$meetingGroup.Controls.Add($meetingGrid)

$deviceKeyText = New-Object System.Windows.Forms.TextBox
Add-RowText -grid $meetingGrid -label "DeviceKey" -control $deviceKeyText

$tokenText = New-Object System.Windows.Forms.TextBox
$tokenText.UseSystemPasswordChar = $true
Add-RowText -grid $meetingGrid -label "Token" -control $tokenText

$meetingUrlText = New-Object System.Windows.Forms.TextBox
$meetingUrlText.Text = "https://meeting.ygsoft.fr/api"
Add-RowText -grid $meetingGrid -label "MeetingApiUrl" -control $meetingUrlText

# Options avancées (collapsable)
$advancedToggle = New-CheckBoxControl "Mode utilisateur avancé (affiche les options expertes)" $false
$advancedToggle.Margin = "0,0,0,8"
$leftPanel.Controls.Add($advancedToggle)

$advancedGroup = New-GroupBoxControl "Options avancées"
$advancedGroup.Visible = $false
$advancedGroup.Height = 250
$leftPanel.Controls.Add($advancedGroup)

$optionsPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$optionsPanel.Dock = "Fill"
$optionsPanel.FlowDirection = "TopDown"
$optionsPanel.WrapContents = $false
$optionsPanel.AutoScroll = $true
$advancedGroup.Controls.Add($optionsPanel)

$cbCheckOnly = New-CheckBoxControl "CheckOnly (connectivité uniquement)"
$cbSkipInstall = New-CheckBoxControl "SkipInstall (transfert sans installer)"
$cbMonitor = New-CheckBoxControl "Monitor (surveillance d'une install en cours)"
$cbNoProvision = New-CheckBoxControl "NoProvision (pas de provisioning)"
$cbNoReboot = New-CheckBoxControl "NoReboot (pas de reboot auto)"
$cbNoBurnToken = New-CheckBoxControl "NoBurnToken (ne pas brûler le token)"

$optionsPanel.Controls.AddRange(@(
    $cbCheckOnly,
    $cbSkipInstall,
    $cbMonitor,
    $cbNoProvision,
    $cbNoReboot,
    $cbNoBurnToken
))

$hint = New-Object System.Windows.Forms.Label
$hint.Text = "Astuce: DeviceKey devient aussi le hostname; cette GUI n'auto-détecte jamais l'IP."
$hint.AutoSize = $true
$hint.MaximumSize = New-Object System.Drawing.Size(420, 0)
$hint.ForeColor = $theme.SubText
$hint.Margin = "3,10,3,3"
$optionsPanel.Controls.Add($hint)

# Progression + commande + logs
$statusGroup = New-GroupBoxControl "Suivi de l'installation"
$statusGroup.Height = 190
$rightPanel.Controls.Add($statusGroup)

$statusLayout = New-Object System.Windows.Forms.TableLayoutPanel
$statusLayout.Dock = "Fill"
$statusLayout.RowCount = 3
$statusLayout.ColumnCount = 1
[void]$statusLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 34)))
[void]$statusLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 26)))
[void]$statusLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$statusGroup.Controls.Add($statusLayout)

$stageLabel = New-Object System.Windows.Forms.Label
$stageLabel.Text = "0% — Prêt"
$stageLabel.AutoSize = $true
$stageLabel.Dock = "Fill"
$stageLabel.TextAlign = "MiddleLeft"
$statusLayout.Controls.Add($stageLabel, 0, 0)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Style = "Continuous"
$progressBar.Height = 18
$progressBar.Value = 0
$statusLayout.Controls.Add($progressBar, 0, 1)

$statusInfo = New-Object System.Windows.Forms.Label
$statusInfo.Text = "Lancez l'installation pour démarrer."
$statusInfo.Dock = "Fill"
$statusInfo.AutoEllipsis = $true
$statusLayout.Controls.Add($statusInfo, 0, 2)

$cmdGroup = New-GroupBoxControl "Commande générée"
$cmdGroup.Height = 140
$rightPanel.Controls.Add($cmdGroup)

$cmdBox = New-Object System.Windows.Forms.TextBox
$cmdBox.Multiline = $true
$cmdBox.ReadOnly = $true
$cmdBox.ScrollBars = "Vertical"
$cmdBox.Dock = "Fill"
$cmdBox.Font = New-Object System.Drawing.Font("Cascadia Mono", 9)
$cmdGroup.Controls.Add($cmdBox)

$logGroup = New-GroupBoxControl "Logs temps réel"
$logGroup.Dock = "Fill"
$rightPanel.Controls.Add($logGroup)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = "Both"
$logBox.Dock = "Fill"
$logBox.Font = New-Object System.Drawing.Font("Cascadia Mono", 9)
$logGroup.Controls.Add($logBox)

$buttonsPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$buttonsPanel.Dock = "Bottom"
$buttonsPanel.Height = 54
$buttonsPanel.FlowDirection = "LeftToRight"
$buttonsPanel.WrapContents = $false
$buttonsPanel.Padding = "10,8,10,8"
$rightPanel.Controls.Add($buttonsPanel)

$btnBuild = New-Object System.Windows.Forms.Button
$btnBuild.Text = "Mettre à jour commande"
$btnBuild.Width = 160

$btnCopy = New-Object System.Windows.Forms.Button
$btnCopy.Text = "Copier"
$btnCopy.Width = 90

$btnRun = New-Object System.Windows.Forms.Button
$btnRun.Text = "Lancer"
$btnRun.Width = 110

$btnStop = New-Object System.Windows.Forms.Button
$btnStop.Text = "Stop"
$btnStop.Width = 90
$btnStop.Enabled = $false

$btnClear = New-Object System.Windows.Forms.Button
$btnClear.Text = "Nettoyer logs"
$btnClear.Width = 120

$btnRestore = New-Object System.Windows.Forms.Button
$btnRestore.Text = "Restaurer"
$btnRestore.Width = 110

$buttonsPanel.Controls.AddRange(@($btnBuild, $btnCopy, $btnRun, $btnStop, $btnClear, $btnRestore))

Set-ThemeColors $form

# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
$script:process = $null
$script:logFilePath = $null
$script:currentRunContext = @{}

function Update-CommandPreview {
    try {
        $installerArgs = Build-InstallerArgs `
            -ip $ipText.Text.Trim() `
            -timezone $timezoneText.Text.Trim() `
            -user $userText.Text.Trim() `
            -password $passwordText.Text `
            -timeoutSec ([int]$timeoutNumeric.Value) `
            -deviceKey $deviceKeyText.Text.Trim() `
            -token $tokenText.Text `
            -meetingApiUrl $meetingUrlText.Text.Trim() `
            -checkOnly $cbCheckOnly.Checked `
            -skipInstall $cbSkipInstall.Checked `
            -monitor $cbMonitor.Checked `
            -noProvision $cbNoProvision.Checked `
            -noReboot $cbNoReboot.Checked `
            -noBurnToken $cbNoBurnToken.Checked

        $psArgs = Build-PowerShellArgumentString -installerArgs $installerArgs
        if ($cmdBox -and -not $cmdBox.IsDisposed) {
            $cmdBox.Text = ("powershell " + $psArgs)
        }
        return @{ InstallerArgs = $installerArgs; PowerShellArgs = $psArgs }
    } catch {
        # Silently ignore errors in command preview
        return @{ InstallerArgs = @(); PowerShellArgs = "" }
    }
}

function Test-Inputs {
    if (-not $ipText.Text.Trim()) {
        Fail "L'adresse IP est obligatoire."
    }
    if ($cbCheckOnly.Checked -and $cbSkipInstall.Checked) {
        Fail "CheckOnly et SkipInstall sont exclusifs."
    }
}

function Set-RunningState([bool]$running) {
    $btnRun.Enabled = -not $running
    $btnStop.Enabled = $running
    $btnBuild.Enabled = -not $running
    $advancedToggle.Enabled = -not $running
    if ($running) {
        $statusInfo.Text = "Installation en cours..."
        Set-Stage -progressBar $progressBar -label $stageLabel -percent 2 -text "Démarrage"
    } else {
        $statusInfo.Text = "Prêt."
    }
}

function Start-HeartbeatCheck {
    param($ctx)
    if (-not ($ctx.DeviceKey) -or -not ($ctx.Token)) {
        Add-LogEntry -textBox $logBox -text "Heartbeat: ignoré (DeviceKey/Token manquants)." -logPath $script:logFilePath
        return
    }

    Add-LogEntry -textBox $logBox -text "Heartbeat: envoi et vérification de l'IP attendue ($($ctx.IP))." -logPath $script:logFilePath
    Set-Stage -progressBar $progressBar -label $stageLabel -percent 96 -text "Validation heartbeat"

    [void][System.Threading.Tasks.Task]::Run({
        $result = Invoke-HeartbeatValidation -DeviceKey $ctx.DeviceKey -Token $ctx.Token -MeetingApiUrl $ctx.MeetingApiUrl -ExpectedIp $ctx.IP -TimeoutSec 120
        $form.BeginInvoke([Action]{
            switch ($result.Status) {
                "ok" {
                    $ip = $result.ReportedIp
                    Add-LogEntry -textBox $logBox -text "Heartbeat OK: IP retournée = ${ip}" -logPath $script:logFilePath
                    Set-Stage -progressBar $progressBar -label $stageLabel -percent 100 -text "Terminé"
                }
                "skipped" {
                    Add-LogEntry -textBox $logBox -text "Heartbeat: non exécuté (paramètres manquants)." -logPath $script:logFilePath
                    Set-Stage -progressBar $progressBar -label $stageLabel -percent 100 -text "Terminé"
                }
                default {
                    $msg = if ($result.Message) { $result.Message } else { "Validation heartbeat non confirmée" }
                    $ip = if ($result.ReportedIp) { $result.ReportedIp } else { "(inconnue)" }
                    Add-LogEntry -textBox $logBox -text "Heartbeat partiel/échec: $msg (IP vue: $ip)" -logPath $script:logFilePath
                    Set-Stage -progressBar $progressBar -label $stageLabel -percent 98 -text "Heartbeat non confirmé"
                }
            }
        }) | Out-Null
    })
}

function Start-Installer {
    # CRITICAL: Write debug info to a separate file for troubleshooting
    $debugLogPath = Join-Path $scriptRoot "logs\debug_installer.log"
    $debugLog = { param($msg) Add-Content -LiteralPath $debugLogPath -Value "[$(Get-Date -Format 'HH:mm:ss.fff')] $msg" -ErrorAction SilentlyContinue }
    & $debugLog "=== START-INSTALLER CALLED ==="
    
    try {
        & $debugLog "Step 1: Test-Inputs"
        Test-Inputs
        
        & $debugLog "Step 2: Save-LastInstallConfig"
        Save-LastInstallConfig -ip $ipText.Text.Trim() -timezone $timezoneText.Text.Trim() -user $userText.Text.Trim() -deviceKey $deviceKeyText.Text.Trim() -meetingApiUrl $meetingUrlText.Text.Trim() -checkOnly $cbCheckOnly.Checked -skipInstall $cbSkipInstall.Checked -monitor $cbMonitor.Checked -noProvision $cbNoProvision.Checked -noReboot $cbNoReboot.Checked -noBurnToken $cbNoBurnToken.Checked
        
        if ($null -ne $script:process -and -not $script:process.HasExited) {
            & $debugLog "ERROR: Process already running"
            Fail "Un processus est déjà en cours."
        }

        & $debugLog "Step 3: Update-CommandPreview"
        $preview = Update-CommandPreview
        & $debugLog "Preview args: $($preview.PowerShellArgs)"
        
        $psExe = (Get-Command powershell).Source
        & $debugLog "PowerShell exe: $psExe"

        $script:logFilePath = New-LogFilePath -ip $ipText.Text.Trim()
        & $debugLog "Log file path: $($script:logFilePath)"
        
        Add-LogEntry -textBox $logBox -text "Logs enregistrés dans $script:logFilePath" -logPath $script:logFilePath

        & $debugLog "Step 4: Creating ProcessStartInfo"
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $psExe
        $psi.Arguments = $preview.PowerShellArgs
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8

        & $debugLog "Step 5: Creating Process object"
        $script:process = New-Object System.Diagnostics.Process
        $script:process.StartInfo = $psi
        $script:process.EnableRaisingEvents = $true

        $script:currentRunContext = @{
            DeviceKey    = $deviceKeyText.Text.Trim()
            Token        = $tokenText.Text.Trim()
            MeetingApiUrl= $meetingUrlText.Text.Trim()
            IP           = $ipText.Text.Trim()
        }
        & $debugLog "Context IP: $($script:currentRunContext.IP)"

        # Store log file path for event handlers
        $logFilePathRef = $script:logFilePath

        & $debugLog "Step 6: Registering OutputDataReceived event"
        # Use ConcurrentQueue for thread-safe communication - NO BeginInvoke!
        $null = Register-ObjectEvent -InputObject $script:process -EventName OutputDataReceived -Action {
            try {
                $data = $Event.SourceEventArgs.Data
                if ($null -ne $data -and $data -ne "") {
                    # Write to debug log
                    Add-Content -LiteralPath $Event.MessageData.DebugLog -Value "[OUT] $data" -ErrorAction SilentlyContinue
                    # Write to main log file
                    $stamp = (Get-Date).ToString('HH:mm:ss')
                    $line = "[$stamp] $data"
                    Add-Content -LiteralPath $Event.MessageData.LogPath -Value $line -ErrorAction SilentlyContinue
                    # Enqueue for UI update (Timer will dequeue and update UI safely)
                    $Event.MessageData.Queue.Enqueue($line)
                }
            } catch {
                Add-Content -LiteralPath $Event.MessageData.DebugLog -Value "[OUT-ERROR] $($_.Exception.Message)" -ErrorAction SilentlyContinue
            }
        } -MessageData @{ LogPath = $logFilePathRef; DebugLog = $debugLogPath; Queue = $script:logQueue }

        & $debugLog "Step 7: Registering ErrorDataReceived event"
        $null = Register-ObjectEvent -InputObject $script:process -EventName ErrorDataReceived -Action {
            try {
                $data = $Event.SourceEventArgs.Data
                if ($null -ne $data -and $data -ne "") {
                    Add-Content -LiteralPath $Event.MessageData.DebugLog -Value "[ERR] $data" -ErrorAction SilentlyContinue
                    $stamp = (Get-Date).ToString('HH:mm:ss')
                    $line = "[$stamp] [stderr] $data"
                    Add-Content -LiteralPath $Event.MessageData.LogPath -Value $line -ErrorAction SilentlyContinue
                    # Enqueue stderr too
                    $Event.MessageData.Queue.Enqueue($line)
                }
            } catch {
                Add-Content -LiteralPath $Event.MessageData.DebugLog -Value "[ERR-ERROR] $($_.Exception.Message)" -ErrorAction SilentlyContinue
            }
        } -MessageData @{ LogPath = $logFilePathRef; DebugLog = $debugLogPath; Queue = $script:logQueue }

        & $debugLog "Step 8: Registering Exited event"
        $null = Register-ObjectEvent -InputObject $script:process -EventName Exited -Action {
            try {
                $code = $Event.SourceEventArgs.ExitCode
                Add-Content -LiteralPath $Event.MessageData.DebugLog -Value "[EXIT] Process exited with code: $code" -ErrorAction SilentlyContinue
                $stamp = (Get-Date).ToString('HH:mm:ss')
                $line = "[$stamp] === Processus terminé avec code $code ==="
                Add-Content -LiteralPath $Event.MessageData.LogPath -Value $line -ErrorAction SilentlyContinue
                $Event.MessageData.Queue.Enqueue($line)
            } catch {
                Add-Content -LiteralPath $Event.MessageData.DebugLog -Value "[EXIT-ERROR] $($_.Exception.Message)" -ErrorAction SilentlyContinue
            }
        } -MessageData @{ LogPath = $logFilePathRef; DebugLog = $debugLogPath; Queue = $script:logQueue }

        Add-LogEntry -textBox $logBox -text "Commande: $($cmdBox.Text)" -logPath $script:logFilePath
        & $debugLog "Step 9: Setting running state"
        Set-RunningState $true

        & $debugLog "Step 10: Starting process"
        $started = $script:process.Start()
        & $debugLog "Process.Start() returned: $started"
        
        if (-not $started) {
            & $debugLog "ERROR: Process failed to start"
            Fail "Impossible de démarrer le processus."
        }
        
        & $debugLog "Step 11: BeginOutputReadLine"
        $script:process.BeginOutputReadLine()
        
        & $debugLog "Step 12: BeginErrorReadLine"
        $script:process.BeginErrorReadLine()
        
        & $debugLog "Step 13: Process started successfully, PID: $($script:process.Id)"
        Add-LogEntry -textBox $logBox -text "Process démarré (PID: $($script:process.Id))" -logPath $script:logFilePath
        
    } catch {
        $errMsg = $_.Exception.Message
        & $debugLog "EXCEPTION: $errMsg"
        & $debugLog "Stack: $($_.ScriptStackTrace)"
        Add-LogEntry -textBox $logBox -text "[ERREUR] $errMsg" -logPath $script:logFilePath
        Set-RunningState $false
    }
}

function Stop-Installer {
    try {
        if ($null -eq $script:process -or $script:process.HasExited) { return }
        Add-LogEntry -textBox $logBox -text "Arrêt du processus..." -logPath $script:logFilePath
        $script:process.Kill()
    } catch {
        Add-LogEntry -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message) -logPath $script:logFilePath
    }
}

# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
$advancedToggle.add_CheckedChanged({
    try {
        $advancedGroup.Visible = $advancedToggle.Checked
    } catch {
        # Silently ignore errors in toggle
    }
})

foreach ($tb in @($ipText, $timezoneText, $userText, $passwordText, $deviceKeyText, $tokenText, $meetingUrlText)) {
    $tb.add_TextChanged({
        try {
            [void](Update-CommandPreview)
        } catch {
            # Silently ignore errors during preview update
        }
    })
}
$timeoutNumeric.add_ValueChanged({
    try {
        [void](Update-CommandPreview)
    } catch {
        # Silently ignore errors during preview update
    }
})
foreach ($cb in @($cbCheckOnly, $cbSkipInstall, $cbMonitor, $cbNoProvision, $cbNoReboot, $cbNoBurnToken)) {
    $cb.add_CheckedChanged({
        try {
            [void](Update-CommandPreview)
        } catch {
            # Silently ignore errors during preview update
        }
    })
}

$btnBuild.Add_Click({
    try {
        [void](Update-CommandPreview)
    } catch {
        try {
            Add-LogEntry -textBox $logBox -text ("[ERREUR Build] " + $_.Exception.Message) -logPath $script:logFilePath
        } catch { }
    }
})

$btnCopy.Add_Click({
    try {
        if (-not $cmdBox.Text) { return }
        [System.Windows.Forms.Clipboard]::SetText($cmdBox.Text)
        $statusInfo.Text = "Commande copiée dans le presse-papiers."
    } catch {
        try {
            $statusInfo.Text = "Erreur lors de la copie."
        } catch { }
    }
})

$btnClear.Add_Click({
    try {
        $logBox.Clear()
        $statusInfo.Text = "Logs nettoyés."
    } catch {
        try {
            $statusInfo.Text = "Erreur lors du nettoyage."
        } catch { }
    }
})

$btnRestore.Add_Click({
    try {
        $lastConfig = Load-LastInstallConfig
        if ($lastConfig) {
            $ipText.Text = $lastConfig.ip
            $timezoneText.Text = $lastConfig.timezone
            $userText.Text = $lastConfig.user
            $deviceKeyText.Text = $lastConfig.deviceKey
            $meetingUrlText.Text = $lastConfig.meetingApiUrl
            $cbCheckOnly.Checked = $lastConfig.checkOnly
            $cbSkipInstall.Checked = $lastConfig.skipInstall
            $cbMonitor.Checked = $lastConfig.monitor
            $cbNoProvision.Checked = $lastConfig.noProvision
            $cbNoReboot.Checked = $lastConfig.noReboot
            $cbNoBurnToken.Checked = $lastConfig.noBurnToken
            $statusInfo.Text = "Configuration restaurée."
            [void](Update-CommandPreview)
        } else {
            $statusInfo.Text = "Aucune configuration précédente disponible."
        }
    } catch {
        try {
            $statusInfo.Text = "Erreur lors de la restauration."
        } catch { }
    }
})

$btnRun.Add_Click({
    try {
        Start-Installer
    } catch {
        try {
            Add-LogEntry -textBox $logBox -text ("[ERREUR Run] " + $_.Exception.Message) -logPath $script:logFilePath
        } catch { }
    }
})

$btnStop.Add_Click({
    try {
        Stop-Installer
    } catch {
        try {
            Add-LogEntry -textBox $logBox -text ("[ERREUR Stop] " + $_.Exception.Message) -logPath $script:logFilePath
        } catch { }
    }
})

$form.add_FormClosing({
    try {
        if ($null -ne $script:process -and -not $script:process.HasExited) {
            $script:process.Kill()
        }
    } catch {
        # Silently ignore errors during form closing
    }
})

# Pre-fill fields from CLI arguments if provided
if ($IP) { $ipText.Text = $IP }
if ($DeviceKey) { $deviceKeyText.Text = $DeviceKey }
if ($Token) { $tokenText.Text = $Token }
if ($MeetingApiUrl) { $meetingUrlText.Text = $MeetingApiUrl }
if ($Timezone) { $timezoneText.Text = $Timezone }
if ($User) { $userText.Text = $User }
if ($Password) { $passwordText.Text = $Password }

[void](Update-CommandPreview)

# Create Timer to dequeue log messages and update UI safely (runs on UI thread)
$script:uiTimer = New-Object System.Windows.Forms.Timer
$script:uiTimer.Interval = 100  # Check every 100ms
$script:uiTimer.add_Tick({
    try {
        Update-LogBoxFromQueue -textBox $logBox
        
        # Also update progress if process is running
        if ($null -ne $script:process -and -not $script:process.HasExited) {
            # Keep UI responsive
            [System.Windows.Forms.Application]::DoEvents()
        } elseif ($null -ne $script:process -and $script:process.HasExited) {
            # Process finished - update running state
            Set-RunningState $false
        }
    } catch { }
})
$script:uiTimer.Start()

# Stop timer when form closes
$form.add_FormClosing({
    try {
        if ($script:uiTimer) {
            $script:uiTimer.Stop()
            $script:uiTimer.Dispose()
        }
    } catch { }
})

# Auto-launch if -Launch flag provided - use Load event instead of BeginInvoke
if ($script:autoLaunchAfterInit) {
    $form.add_Load({
        Start-Sleep -Milliseconds 1000
        try { Start-Installer } catch { }
    })
}

[void]$form.ShowDialog()

} catch {
    Write-Host "Erreur: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
