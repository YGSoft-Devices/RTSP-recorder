# debug_tools_gui.ps1 - GUI Windows pour les outils debug_tools/
# Version: 1.2.8
#
# Usage:
#   .\debug_tools\debug_tools_gui.ps1
#
# Prérequis:
#   - Windows 10/11 x64
#   - Windows PowerShell 5.1 (recommandé) ou PowerShell 7 sur Windows

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:OS -notlike "*Windows*") {
    throw "Ce script GUI est prévu pour Windows."
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Fail([string]$message) {
    [System.Windows.Forms.MessageBox]::Show(
        $message,
        "RTSP-Full - Debug Tools (GUI)",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    throw $message
}

function Append-TextSafely {
    param(
        [System.Windows.Forms.TextBox]$textBox,
        [string]$text
    )
    if ($textBox.IsDisposed) { return }
    $action = [Action]{
        $textBox.AppendText($text)
        $textBox.SelectionStart = $textBox.TextLength
        $textBox.ScrollToCaret()
    }
    [void]$textBox.BeginInvoke($action)
}

function Encode-Command([string]$command) {
    [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($command))
}

function Quote-PowerShellSingle([string]$value) {
    if ($null -eq $value) { return "''" }
    "'" + ($value -replace "'", "''") + "'"
}

function Quote-CmdArg([string]$value) {
    if ($null -eq $value) { return '""' }
    return '"' + ($value -replace '"', '""') + '"'
}

function Get-MeetingField {
    param(
        [object]$Object,
        [string]$Name
    )
    if ($null -eq $Object -or -not $Name) { return $null }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $null
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $null
}

function Build-EncodedScriptInvocation {
    param(
        [Parameter(Mandatory=$true)][string]$ScriptPath,
        [string[]]$ScriptArgs
    )

    if (-not (Test-Path -LiteralPath $ScriptPath)) {
        Fail "Script introuvable: $ScriptPath"
    }

    $argLiterals = New-Object System.Collections.Generic.List[string]
    foreach ($a in ($ScriptArgs | Where-Object { $null -ne $_ })) {
        [void]$argLiterals.Add((Quote-PowerShellSingle $a))
    }

    $argsArray = if ($argLiterals.Count -gt 0) { "@(" + ($argLiterals -join ", ") + ")" } else { "@()" }

    $payload = @"
`$ErrorActionPreference = 'Stop'
`$argsList = $argsArray
& $(Quote-PowerShellSingle $ScriptPath) @argsList
exit `$LASTEXITCODE
"@
    "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $(Encode-Command $payload)"
}

$scriptRoot = Split-Path -Parent $PSCommandPath
$paths = @{
    InstallDevice = Join-Path $scriptRoot "install_device.ps1"
    InstallDeviceGui = Join-Path $scriptRoot "install_device_gui.ps1"
    RunRemote = Join-Path $scriptRoot "run_remote.ps1"
    DeployScp = Join-Path $scriptRoot "deploy_scp.ps1"
    SshDevice = Join-Path $scriptRoot "ssh_device.ps1"
    GetLogs = Join-Path $scriptRoot "get_logs.ps1"
    ConfigTool = Join-Path $scriptRoot "config_tool.ps1"
    UpdateDevice = Join-Path $scriptRoot "update_device.ps1"
    StopServices = Join-Path $scriptRoot "stop_services.sh"
    MeetingConfig = Join-Path $scriptRoot "meeting_config.json"
    DeviceMemory = Join-Path $scriptRoot "device_memory.json"
}

foreach ($k in @("InstallDevice","InstallDeviceGui","RunRemote","DeployScp","SshDevice","GetLogs","ConfigTool","UpdateDevice")) {
    if (-not (Test-Path -LiteralPath $paths[$k])) {
        Fail "Fichier requis introuvable: $($paths[$k])"
    }
}

$psExe = (Get-Command powershell -ErrorAction SilentlyContinue).Source
if (-not $psExe) { Fail "powershell.exe introuvable." }

function Load-MeetingConfig {
    $defaultUrl = "https://meeting.ygsoft.fr/api"
    if (-not (Test-Path -LiteralPath $paths.MeetingConfig)) {
        return @{ api_url = $defaultUrl; device_key = ""; token_code = "" }
    }
    try {
        $cfg = Get-Content -LiteralPath $paths.MeetingConfig -Raw | ConvertFrom-Json
        $apiUrl = if ($cfg.api_url) { [string]$cfg.api_url } else { $defaultUrl }
        return @{
            api_url = $apiUrl
            device_key = [string]$cfg.device_key
            token_code = [string]$cfg.token_code
        }
    } catch {
        return @{ api_url = $defaultUrl; device_key = ""; token_code = "" }
    }
}

function Save-MeetingConfig {
    param([string]$ApiUrl,[string]$DeviceKey,[string]$TokenCode)
    @{ api_url = $ApiUrl; device_key = $DeviceKey; token_code = $TokenCode } |
        ConvertTo-Json | Set-Content -LiteralPath $paths.MeetingConfig -Encoding UTF8
}

function Load-DeviceMemory {
    if (-not (Test-Path -LiteralPath $paths.DeviceMemory)) {
        return @()
    }
    try {
        $data = Get-Content -LiteralPath $paths.DeviceMemory -Raw | ConvertFrom-Json
        if ($data -is [System.Collections.IEnumerable]) { return @($data) }
        return @()
    } catch {
        return @()
    }
}

function Save-DeviceMemory {
    param([array]$Entries)
    $payload = @($Entries) | ConvertTo-Json -Depth 4
    $payload | Set-Content -LiteralPath $paths.DeviceMemory -Encoding UTF8
}

function Upsert-DeviceMemory {
    param(
        [string]$DeviceKey,
        [string]$Ip,
        [string]$Online
    )
    $entries = Load-DeviceMemory
    $now = (Get-Date).ToString("s")
    $found = $false
    foreach ($e in $entries) {
        $entryKey = if ($e.PSObject.Properties.Match('device_key')) { $e.device_key } else { "" }
        $entryIp = if ($e.PSObject.Properties.Match('ip')) { $e.ip } else { "" }
        if ($DeviceKey -and $entryKey -eq $DeviceKey) {
            if ($Ip) {
                if ($e.PSObject.Properties.Match('ip')) { $e.ip = $Ip }
                else { $e | Add-Member -NotePropertyName ip -NotePropertyValue $Ip -Force }
            }
            if ($Online -ne $null) {
                if ($e.PSObject.Properties.Match('online')) { $e.online = $Online }
                else { $e | Add-Member -NotePropertyName online -NotePropertyValue $Online -Force }
            }
            if ($e.PSObject.Properties.Match('last_seen')) { $e.last_seen = $now }
            else { $e | Add-Member -NotePropertyName last_seen -NotePropertyValue $now -Force }
            $found = $true
            break
        }
        if (-not $DeviceKey -and $Ip -and $entryIp -eq $Ip) {
            if ($Online -ne $null) {
                if ($e.PSObject.Properties.Match('online')) { $e.online = $Online }
                else { $e | Add-Member -NotePropertyName online -NotePropertyValue $Online -Force }
            }
            if ($e.PSObject.Properties.Match('last_seen')) { $e.last_seen = $now }
            else { $e | Add-Member -NotePropertyName last_seen -NotePropertyValue $now -Force }
            $found = $true
            break
        }
    }
    if (-not $found) {
        $entries += [pscustomobject]@{
            device_key = $DeviceKey
            ip = $Ip
            online = $Online
            last_seen = $now
        }
    }
    Save-DeviceMemory -Entries $entries
    return $entries
}

function Invoke-MeetingDeviceLookup {
    param(
        [string]$DeviceKey,
        [string]$ApiUrl,
        [string]$TokenCode
    )
    if (-not $DeviceKey -or -not $ApiUrl) { return $null }
    try {
        $url = "$($ApiUrl.TrimEnd('/'))/devices/$DeviceKey"
        if ($TokenCode) {
            $headers = @{ "X-Token-Code" = $TokenCode; "Accept" = "application/json" }
            return Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 5 -ErrorAction Stop
        }
        return Invoke-RestMethod -Uri $url -TimeoutSec 5 -ErrorAction Stop
    } catch {
        return $null
    }
}

function New-SectionHeader([string]$Text) {
    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = $Text
    $lbl.AutoSize = $true
    $lbl.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
    $lbl.Margin = "3,10,3,6"
    $lbl
}

function New-Row {
    param(
        [System.Windows.Forms.TableLayoutPanel]$Table,
        [string]$Label,
        [System.Windows.Forms.Control]$Control
    )
    $row = $Table.RowCount
    $Table.RowCount = $row + 1
    [void]$Table.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = $Label
    $lbl.AutoSize = $true
    $lbl.Margin = "3,6,6,6"

    $Control.Dock = "Fill"
    $Control.Margin = "3,3,3,3"

    $Table.Controls.Add($lbl, 0, $row)
    $Table.Controls.Add($Control, 1, $row)
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "RTSP-Full — Debug Tools (GUI)"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(1100, 780)
$form.MinimumSize = New-Object System.Drawing.Size(1100, 780)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$layout = New-Object System.Windows.Forms.TableLayoutPanel
$layout.Dock = "Fill"
$layout.ColumnCount = 2
$layout.RowCount = 2
[void]$layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 46)))
[void]$layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 54)))
[void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
[void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 56)))
$form.Controls.Add($layout)

$tabs = New-Object System.Windows.Forms.TabControl
$tabs.Dock = "Fill"
$layout.Controls.Add($tabs, 0, 0)

$rightPanel = New-Object System.Windows.Forms.Panel
$rightPanel.Dock = "Fill"
$layout.Controls.Add($rightPanel, 1, 0)

$cmdGroup = New-Object System.Windows.Forms.GroupBox
$cmdGroup.Text = "Commande (preview)"
$cmdGroup.Dock = "Top"
$cmdGroup.Height = 90
$rightPanel.Controls.Add($cmdGroup)

$cmdBox = New-Object System.Windows.Forms.TextBox
$cmdBox.Multiline = $true
$cmdBox.ReadOnly = $true
$cmdBox.ScrollBars = "Vertical"
$cmdBox.Dock = "Fill"
$cmdBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$cmdGroup.Controls.Add($cmdBox)

$logGroup = New-Object System.Windows.Forms.GroupBox
$logGroup.Text = "Logs (stdout/stderr)"
$logGroup.Dock = "Fill"
$rightPanel.Controls.Add($logGroup)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ReadOnly = $true
$logBox.ScrollBars = "Both"
$logBox.Dock = "Fill"
$logBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$logGroup.Controls.Add($logBox)

$buttons = New-Object System.Windows.Forms.FlowLayoutPanel
$buttons.Dock = "Fill"
$buttons.FlowDirection = "LeftToRight"
$buttons.WrapContents = $false
$buttons.Padding = "10,10,10,10"
$layout.Controls.Add($buttons, 0, 1)
$layout.SetColumnSpan($buttons, 2)

$btnBuild = New-Object System.Windows.Forms.Button; $btnBuild.Text = "Générer"; $btnBuild.Width = 110
$btnCopy = New-Object System.Windows.Forms.Button; $btnCopy.Text = "Copier"; $btnCopy.Width = 110
$btnRun = New-Object System.Windows.Forms.Button; $btnRun.Text = "Lancer"; $btnRun.Width = 110
$btnStop = New-Object System.Windows.Forms.Button; $btnStop.Text = "Stop"; $btnStop.Width = 110; $btnStop.Enabled = $false
$btnClear = New-Object System.Windows.Forms.Button; $btnClear.Text = "Nettoyer logs"; $btnClear.Width = 140
$buttons.Controls.AddRange(@($btnBuild,$btnCopy,$btnRun,$btnStop,$btnClear))

$process = $null
$script:CurrentInvocation = $null

function Set-RunningState([bool]$running) {
    $btnRun.Enabled = -not $running
    $btnStop.Enabled = $running
    $btnBuild.Enabled = -not $running
    $tabs.Enabled = -not $running
}

function Start-LoggedProcess([string]$Title,[string]$Arguments) {
    if ($null -ne $process -and -not $process.HasExited) { Fail "Un processus est déjà en cours." }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $psExe
    $psi.Arguments = $Arguments
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $process.EnableRaisingEvents = $true

    $process.add_OutputDataReceived({
        if ($null -ne $EventArgs.Data) { Append-TextSafely -textBox $logBox -text ($EventArgs.Data + [Environment]::NewLine) }
    })
    $process.add_ErrorDataReceived({
        if ($null -ne $EventArgs.Data) { Append-TextSafely -textBox $logBox -text ("[stderr] " + $EventArgs.Data + [Environment]::NewLine) }
    })
    $process.add_Exited({
        $code = $process.ExitCode
        Append-TextSafely -textBox $logBox -text ("`r`n[Process exited] code=$code" + [Environment]::NewLine)
        $form.BeginInvoke([Action]{ Set-RunningState $false }) | Out-Null
    })

    Append-TextSafely -textBox $logBox -text ("`r`n[Starting] $Title`r`n$($cmdBox.Text)`r`n`r`n")
    if (-not $process.Start()) { Fail "Impossible de démarrer le processus." }
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    Set-RunningState $true
}

# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------

# Tab: Meeting/IP
$tabMeeting = New-Object System.Windows.Forms.TabPage
$tabMeeting.Text = "Meeting/IP"
$tabs.TabPages.Add($tabMeeting) | Out-Null

$mLayout = New-Object System.Windows.Forms.TableLayoutPanel
$mLayout.Dock = "Fill"
$mLayout.ColumnCount = 2
$mLayout.RowCount = 0
[void]$mLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$mLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabMeeting.Controls.Add($mLayout)

$mLayout.Controls.Add((New-SectionHeader "meeting_config.json"), 0, 0)
$mLayout.SetColumnSpan($mLayout.Controls[$mLayout.Controls.Count-1], 2)
$mLayout.RowCount = 1
[void]$mLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$mApi = New-Object System.Windows.Forms.TextBox
$mKey = New-Object System.Windows.Forms.TextBox
$mToken = New-Object System.Windows.Forms.TextBox
$mToken.UseSystemPasswordChar = $true
$mIp = New-Object System.Windows.Forms.TextBox

New-Row -Table $mLayout -Label "API URL" -Control $mApi
New-Row -Table $mLayout -Label "DeviceKey" -Control $mKey
New-Row -Table $mLayout -Label "Token" -Control $mToken
New-Row -Table $mLayout -Label "Device IP" -Control $mIp

$mBtns = New-Object System.Windows.Forms.FlowLayoutPanel
$mBtns.Dock = "Top"
$mBtns.WrapContents = $false

$btnMLoad = New-Object System.Windows.Forms.Button; $btnMLoad.Text = "Charger"; $btnMLoad.Width = 110
$btnMSave = New-Object System.Windows.Forms.Button; $btnMSave.Text = "Sauvegarder"; $btnMSave.Width = 110
$btnMOpen = New-Object System.Windows.Forms.Button; $btnMOpen.Text = "Ouvrir dossier"; $btnMOpen.Width = 130
$mBtns.Controls.AddRange(@($btnMLoad,$btnMSave,$btnMOpen))

$row = $mLayout.RowCount
$mLayout.RowCount = $row + 1
[void]$mLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$mLayout.Controls.Add($mBtns, 0, $row)
$mLayout.SetColumnSpan($mBtns, 2)

$btnMLoad.Add_Click({
    $cfg = Load-MeetingConfig
    $mApi.Text = $cfg.api_url
    $mKey.Text = $cfg.device_key
    $mToken.Text = $cfg.token_code
})

$btnMSave.Add_Click({
    try {
        Save-MeetingConfig -ApiUrl $mApi.Text.Trim() -DeviceKey $mKey.Text.Trim() -TokenCode $mToken.Text
        Append-TextSafely -textBox $logBox -text ("[Meeting] Config sauvegardée: $($paths.MeetingConfig)" + [Environment]::NewLine)
    } catch {
        Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
    }
})

$btnMOpen.Add_Click({ try { Start-Process explorer.exe $scriptRoot | Out-Null } catch { } })

$cfg0 = Load-MeetingConfig
$mApi.Text = $cfg0.api_url
$mKey.Text = $cfg0.device_key
$mToken.Text = $cfg0.token_code

$mLayout.Controls.Add((New-SectionHeader "Device memory"), 0, $mLayout.RowCount)
$mLayout.SetColumnSpan($mLayout.Controls[$mLayout.Controls.Count-1], 2)
$mLayout.RowCount += 1
[void]$mLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$memList = New-Object System.Windows.Forms.ListView
$memList.View = "Details"
$memList.FullRowSelect = $true
$memList.GridLines = $true
$memList.Height = 180
$memList.Columns.Add("DeviceKey", 260) | Out-Null
$memList.Columns.Add("IP", 120) | Out-Null
$memList.Columns.Add("Online", 80) | Out-Null
$memList.Columns.Add("LastSeen", 140) | Out-Null

$memPanel = New-Object System.Windows.Forms.Panel
$memPanel.Dock = "Top"
$memPanel.Height = 190
$memPanel.Controls.Add($memList)
$memList.Dock = "Fill"

$row = $mLayout.RowCount
$mLayout.RowCount = $row + 1
[void]$mLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$mLayout.Controls.Add($memPanel, 0, $row)
$mLayout.SetColumnSpan($memPanel, 2)

$memButtons = New-Object System.Windows.Forms.FlowLayoutPanel
$memButtons.Dock = "Top"
$memButtons.WrapContents = $false
$btnMemUse = New-Object System.Windows.Forms.Button; $btnMemUse.Text = "Utiliser sélection"; $btnMemUse.Width = 140
$btnMemSave = New-Object System.Windows.Forms.Button; $btnMemSave.Text = "Sauver courant"; $btnMemSave.Width = 120
$btnMemRefresh = New-Object System.Windows.Forms.Button; $btnMemRefresh.Text = "Refresh status"; $btnMemRefresh.Width = 130
$btnMemRemove = New-Object System.Windows.Forms.Button; $btnMemRemove.Text = "Supprimer"; $btnMemRemove.Width = 110
$memButtons.Controls.AddRange(@($btnMemUse,$btnMemSave,$btnMemRefresh,$btnMemRemove))

$row = $mLayout.RowCount
$mLayout.RowCount = $row + 1
[void]$mLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$mLayout.Controls.Add($memButtons, 0, $row)
$mLayout.SetColumnSpan($memButtons, 2)

# Tab: Install
$tabInstall = New-Object System.Windows.Forms.TabPage
$tabInstall.Text = "Install"
$tabs.TabPages.Add($tabInstall) | Out-Null

$iLayout = New-Object System.Windows.Forms.TableLayoutPanel
$iLayout.Dock = "Fill"
$iLayout.ColumnCount = 2
$iLayout.RowCount = 0
[void]$iLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$iLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabInstall.Controls.Add($iLayout)

$iLayout.Controls.Add((New-SectionHeader "install_device.ps1"), 0, 0)
$iLayout.SetColumnSpan($iLayout.Controls[$iLayout.Controls.Count-1], 2)
$iLayout.RowCount = 1
[void]$iLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$iIp = New-Object System.Windows.Forms.TextBox
$iTz = New-Object System.Windows.Forms.TextBox; $iTz.Text = "Europe/Paris"
$iUser = New-Object System.Windows.Forms.TextBox; $iUser.Text = "device"
$iPass = New-Object System.Windows.Forms.TextBox; $iPass.Text = "meeting"; $iPass.UseSystemPasswordChar = $true
$iTimeout = New-Object System.Windows.Forms.NumericUpDown; $iTimeout.Minimum = 1; $iTimeout.Maximum = 120; $iTimeout.Value = 10
$iKey = New-Object System.Windows.Forms.TextBox
$iToken = New-Object System.Windows.Forms.TextBox; $iToken.UseSystemPasswordChar = $true
$iUrl = New-Object System.Windows.Forms.TextBox; $iUrl.Text = "https://meeting.ygsoft.fr/api"

New-Row -Table $iLayout -Label "IP (opt)" -Control $iIp
New-Row -Table $iLayout -Label "Timezone" -Control $iTz
New-Row -Table $iLayout -Label "User" -Control $iUser
New-Row -Table $iLayout -Label "Password" -Control $iPass
New-Row -Table $iLayout -Label "Timeout (s)" -Control $iTimeout
New-Row -Table $iLayout -Label "DeviceKey" -Control $iKey
New-Row -Table $iLayout -Label "Token" -Control $iToken
New-Row -Table $iLayout -Label "Meeting URL" -Control $iUrl

$iFlags = New-Object System.Windows.Forms.FlowLayoutPanel
$iFlags.Dock = "Top"
$cbICheckOnly = New-Object System.Windows.Forms.CheckBox; $cbICheckOnly.Text = "CheckOnly"
$cbISkipInstall = New-Object System.Windows.Forms.CheckBox; $cbISkipInstall.Text = "SkipInstall"
$cbIMonitor = New-Object System.Windows.Forms.CheckBox; $cbIMonitor.Text = "Monitor"
$cbINoProvision = New-Object System.Windows.Forms.CheckBox; $cbINoProvision.Text = "NoProvision"
$cbINoReboot = New-Object System.Windows.Forms.CheckBox; $cbINoReboot.Text = "NoReboot"
$cbINoBurnToken = New-Object System.Windows.Forms.CheckBox; $cbINoBurnToken.Text = "NoBurnToken"
$iFlags.Controls.AddRange(@($cbICheckOnly,$cbISkipInstall,$cbIMonitor,$cbINoProvision,$cbINoReboot,$cbINoBurnToken))

$row = $iLayout.RowCount
$iLayout.RowCount = $row + 1
[void]$iLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$iLayout.Controls.Add($iFlags, 0, $row)
$iLayout.SetColumnSpan($iFlags, 2)

$btnOpenInstallGui = New-Object System.Windows.Forms.Button
$btnOpenInstallGui.Text = "Ouvrir install_device_gui.ps1"
$btnOpenInstallGui.Dock = "Top"
$btnOpenInstallGui.Height = 30
$btnOpenInstallGui.Margin = "3,12,3,3"
$row = $iLayout.RowCount
$iLayout.RowCount = $row + 1
[void]$iLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$iLayout.Controls.Add($btnOpenInstallGui, 0, $row)
$iLayout.SetColumnSpan($btnOpenInstallGui, 2)

$btnOpenInstallGui.Add_Click({
    try {
        $args = Build-EncodedScriptInvocation -ScriptPath $paths.InstallDeviceGui -ScriptArgs @()
        $cmdBox.Text = "powershell $args"
        Start-LoggedProcess -Title "install_device_gui.ps1" -Arguments $args
    } catch {
        Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
    }
})

# Tab: Run remote
$tabRun = New-Object System.Windows.Forms.TabPage
$tabRun.Text = "Run remote"
$tabs.TabPages.Add($tabRun) | Out-Null

$rLayout = New-Object System.Windows.Forms.TableLayoutPanel
$rLayout.Dock = "Fill"
$rLayout.ColumnCount = 2
$rLayout.RowCount = 0
[void]$rLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$rLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabRun.Controls.Add($rLayout)

$rLayout.Controls.Add((New-SectionHeader "run_remote.ps1"), 0, 0)
$rLayout.SetColumnSpan($rLayout.Controls[$rLayout.Controls.Count-1], 2)
$rLayout.RowCount = 1
[void]$rLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$rCmd = New-Object System.Windows.Forms.TextBox
$rCmd.Multiline = $true
$rCmd.Height = 80

$rMode = New-Object System.Windows.Forms.FlowLayoutPanel
$rMode.Dock = "Top"
$rbRAuto = New-Object System.Windows.Forms.RadioButton; $rbRAuto.Text = "Auto (Meeting)"; $rbRAuto.Checked = $true
$rbRWifi = New-Object System.Windows.Forms.RadioButton; $rbRWifi.Text = "WiFi"
$rbRIp = New-Object System.Windows.Forms.RadioButton; $rbRIp.Text = "IP"
$rMode.Controls.AddRange(@($rbRAuto,$rbRWifi,$rbRIp))

$rIp = New-Object System.Windows.Forms.TextBox
$rTimeout = New-Object System.Windows.Forms.NumericUpDown
$rTimeout.Minimum = 1
$rTimeout.Maximum = 600
$rTimeout.Value = 30

New-Row -Table $rLayout -Label "Commande" -Control $rCmd
New-Row -Table $rLayout -Label "Mode" -Control $rMode
New-Row -Table $rLayout -Label "IP (si mode IP)" -Control $rIp
New-Row -Table $rLayout -Label "Timeout (s)" -Control $rTimeout

# Tab: Deploy (SCP)
$tabScp = New-Object System.Windows.Forms.TabPage
$tabScp.Text = "Deploy (SCP)"
$tabs.TabPages.Add($tabScp) | Out-Null

$sLayout = New-Object System.Windows.Forms.TableLayoutPanel
$sLayout.Dock = "Fill"
$sLayout.ColumnCount = 2
$sLayout.RowCount = 0
[void]$sLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$sLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabScp.Controls.Add($sLayout)

$sLayout.Controls.Add((New-SectionHeader "deploy_scp.ps1"), 0, 0)
$sLayout.SetColumnSpan($sLayout.Controls[$sLayout.Controls.Count-1], 2)
$sLayout.RowCount = 1
[void]$sLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$sSource = New-Object System.Windows.Forms.TextBox
$sDest = New-Object System.Windows.Forms.TextBox
$sUser = New-Object System.Windows.Forms.TextBox; $sUser.Text = "device"
$sPass = New-Object System.Windows.Forms.TextBox; $sPass.Text = "meeting"; $sPass.UseSystemPasswordChar = $true
$sIpEth = New-Object System.Windows.Forms.TextBox; $sIpEth.Text = "192.168.1.202"
$sIpWifi = New-Object System.Windows.Forms.TextBox; $sIpWifi.Text = "192.168.1.127"

$sOpts = New-Object System.Windows.Forms.FlowLayoutPanel
$sOpts.Dock = "Top"
$rbSAuto = New-Object System.Windows.Forms.RadioButton; $rbSAuto.Text = "Auto (Meeting)"; $rbSAuto.Checked = $true
$rbSWifi = New-Object System.Windows.Forms.RadioButton; $rbSWifi.Text = "WiFi"
$rbSEth = New-Object System.Windows.Forms.RadioButton; $rbSEth.Text = "Ethernet"
$cbSRec = New-Object System.Windows.Forms.CheckBox; $cbSRec.Text = "Recursive"
$cbSDry = New-Object System.Windows.Forms.CheckBox; $cbSDry.Text = "DryRun"
$cbSNoR = New-Object System.Windows.Forms.CheckBox; $cbSNoR.Text = "NoRestart"
$sOpts.Controls.AddRange(@($rbSAuto,$rbSWifi,$rbSEth,$cbSRec,$cbSDry,$cbSNoR))

$sBrowse = New-Object System.Windows.Forms.FlowLayoutPanel
$sBrowse.Dock = "Top"
$sBrowse.WrapContents = $false
$btnSFile = New-Object System.Windows.Forms.Button; $btnSFile.Text = "Fichier..."; $btnSFile.Width = 90
$btnSDir = New-Object System.Windows.Forms.Button; $btnSDir.Text = "Dossier..."; $btnSDir.Width = 90
$sBrowse.Controls.AddRange(@($btnSFile,$btnSDir))

New-Row -Table $sLayout -Label "Source" -Control $sSource
$row = $sLayout.RowCount
$sLayout.RowCount = $row + 1
[void]$sLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$sLayout.Controls.Add($sBrowse, 1, $row)

New-Row -Table $sLayout -Label "Dest (remote)" -Control $sDest
New-Row -Table $sLayout -Label "Options" -Control $sOpts
New-Row -Table $sLayout -Label "User" -Control $sUser
New-Row -Table $sLayout -Label "Password" -Control $sPass
New-Row -Table $sLayout -Label "IP Ethernet" -Control $sIpEth
New-Row -Table $sLayout -Label "IP WiFi" -Control $sIpWifi

$btnSFile.Add_Click({
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $sSource.Text = $dlg.FileName }
})

$btnSDir.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $sSource.Text = (Join-Path $dlg.SelectedPath "*")
        $cbSRec.Checked = $true
    }
})

# Tab: Update
$tabUpdate = New-Object System.Windows.Forms.TabPage
$tabUpdate.Text = "Update"
$tabs.TabPages.Add($tabUpdate) | Out-Null

$uLayout = New-Object System.Windows.Forms.TableLayoutPanel
$uLayout.Dock = "Fill"
$uLayout.ColumnCount = 2
$uLayout.RowCount = 0
[void]$uLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$uLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabUpdate.Controls.Add($uLayout)

$uLayout.Controls.Add((New-SectionHeader "update_device.ps1"), 0, 0)
$uLayout.SetColumnSpan($uLayout.Controls[$uLayout.Controls.Count-1], 2)
$uLayout.RowCount = 1
[void]$uLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$uDeviceKey = New-Object System.Windows.Forms.TextBox
$uIp = New-Object System.Windows.Forms.TextBox
$uToken = New-Object System.Windows.Forms.TextBox
$uToken.UseSystemPasswordChar = $true
$uApiUrl = New-Object System.Windows.Forms.TextBox

$uUser = New-Object System.Windows.Forms.TextBox; $uUser.Text = "device"
$uPass = New-Object System.Windows.Forms.TextBox; $uPass.Text = "meeting"; $uPass.UseSystemPasswordChar = $true
$uFallback = New-Object System.Windows.Forms.TextBox; $uFallback.Text = "192.168.1.202"

$uOpts = New-Object System.Windows.Forms.FlowLayoutPanel
$uOpts.Dock = "Top"
$uOpts.WrapContents = $false
$cbUDry = New-Object System.Windows.Forms.CheckBox; $cbUDry.Text = "DryRun"
$cbUNoRestart = New-Object System.Windows.Forms.CheckBox; $cbUNoRestart.Text = "NoRestart"
$uOpts.Controls.AddRange(@($cbUDry,$cbUNoRestart))

New-Row -Table $uLayout -Label "DeviceKey" -Control $uDeviceKey
New-Row -Table $uLayout -Label "IP (opt)" -Control $uIp
New-Row -Table $uLayout -Label "Token (opt)" -Control $uToken
New-Row -Table $uLayout -Label "API URL" -Control $uApiUrl
New-Row -Table $uLayout -Label "User" -Control $uUser
New-Row -Table $uLayout -Label "Password" -Control $uPass
New-Row -Table $uLayout -Label "Fallback IP" -Control $uFallback
New-Row -Table $uLayout -Label "Options" -Control $uOpts

$cfgUpdate = Load-MeetingConfig
$uApiUrl.Text = $cfgUpdate.api_url
$uToken.Text = $cfgUpdate.token_code

# Tab: SSH
$tabSsh = New-Object System.Windows.Forms.TabPage
$tabSsh.Text = "SSH"
$tabs.TabPages.Add($tabSsh) | Out-Null

$shLayout = New-Object System.Windows.Forms.TableLayoutPanel
$shLayout.Dock = "Fill"
$shLayout.ColumnCount = 2
$shLayout.RowCount = 0
[void]$shLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$shLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabSsh.Controls.Add($shLayout)

$shLayout.Controls.Add((New-SectionHeader "ssh_device.ps1"), 0, 0)
$shLayout.SetColumnSpan($shLayout.Controls[$shLayout.Controls.Count-1], 2)
$shLayout.RowCount = 1
[void]$shLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$shCmd = New-Object System.Windows.Forms.TextBox
$shUseWifi = New-Object System.Windows.Forms.CheckBox; $shUseWifi.Text = "UseWifi"
$shUser = New-Object System.Windows.Forms.TextBox; $shUser.Text = "device"
$shPass = New-Object System.Windows.Forms.TextBox; $shPass.Text = "meeting"; $shPass.UseSystemPasswordChar = $true
$shIpEth = New-Object System.Windows.Forms.TextBox; $shIpEth.Text = "192.168.1.202"
$shIpWifi = New-Object System.Windows.Forms.TextBox; $shIpWifi.Text = "192.168.1.124"

New-Row -Table $shLayout -Label "Commande (opt)" -Control $shCmd
New-Row -Table $shLayout -Label "UseWifi" -Control $shUseWifi
New-Row -Table $shLayout -Label "User" -Control $shUser
New-Row -Table $shLayout -Label "Password" -Control $shPass
New-Row -Table $shLayout -Label "IP Ethernet" -Control $shIpEth
New-Row -Table $shLayout -Label "IP WiFi" -Control $shIpWifi

$sshButtons = New-Object System.Windows.Forms.FlowLayoutPanel
$sshButtons.Dock = "Top"
$sshButtons.WrapContents = $false
$btnSshWindow = New-Object System.Windows.Forms.Button; $btnSshWindow.Text = "Ouvrir SSH (fenetre)"; $btnSshWindow.Width = 180
$sshButtons.Controls.Add($btnSshWindow)

$row = $shLayout.RowCount
$shLayout.RowCount = $row + 1
[void]$shLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$shLayout.Controls.Add($sshButtons, 1, $row)

$btnSshWindow.Add_Click({
    try {
        $args = New-Object System.Collections.Generic.List[string]
        [void]$args.Add("-NoProfile")
        [void]$args.Add("-ExecutionPolicy")
        [void]$args.Add("Bypass")
        [void]$args.Add("-File")
        [void]$args.Add($paths.SshDevice)
        if ($shCmd.Text.Trim()) { [void]$args.Add("-Command"); [void]$args.Add($shCmd.Text.Trim()) }
        if ($shUseWifi.Checked) { [void]$args.Add("-UseWifi") }
        if ($shUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($shUser.Text.Trim()) }
        if ($shPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($shPass.Text) }
        if ($shIpEth.Text.Trim()) { [void]$args.Add("-IpEthernet"); [void]$args.Add($shIpEth.Text.Trim()) }
        if ($shIpWifi.Text.Trim()) { [void]$args.Add("-IpWifi"); [void]$args.Add($shIpWifi.Text.Trim()) }

        $argString = ($args | ForEach-Object { Quote-CmdArg $_ }) -join " "
        Start-Process -FilePath $psExe -ArgumentList $argString -WorkingDirectory $scriptRoot | Out-Null
    } catch {
        Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
    }
})

# Tab: Logs/Diag
$tabLogs = New-Object System.Windows.Forms.TabPage
$tabLogs.Text = "Logs/Diag"
$tabs.TabPages.Add($tabLogs) | Out-Null

$lLayout = New-Object System.Windows.Forms.TableLayoutPanel
$lLayout.Dock = "Fill"
$lLayout.ColumnCount = 2
$lLayout.RowCount = 0
[void]$lLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$lLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabLogs.Controls.Add($lLayout)

$lLayout.Controls.Add((New-SectionHeader "get_logs.ps1"), 0, 0)
$lLayout.SetColumnSpan($lLayout.Controls[$lLayout.Controls.Count-1], 2)
$lLayout.RowCount = 1
[void]$lLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$lTool = New-Object System.Windows.Forms.ComboBox
$lTool.DropDownStyle = "DropDownList"
$lTool.Items.AddRange(@("logs","collect","status","info","dmesg","camera","audio","network","rtsp"))
$lTool.SelectedItem = "logs"
$lService = New-Object System.Windows.Forms.TextBox
$lLines = New-Object System.Windows.Forms.NumericUpDown; $lLines.Minimum = 10; $lLines.Maximum = 5000; $lLines.Value = 200
$lFollow = New-Object System.Windows.Forms.CheckBox; $lFollow.Text = "Follow"

$lMode = New-Object System.Windows.Forms.FlowLayoutPanel; $lMode.Dock = "Top"
$rbLAuto = New-Object System.Windows.Forms.RadioButton; $rbLAuto.Text = "Auto (Meeting)"; $rbLAuto.Checked = $true
$rbLWifi = New-Object System.Windows.Forms.RadioButton; $rbLWifi.Text = "WiFi"
$rbLIp = New-Object System.Windows.Forms.RadioButton; $rbLIp.Text = "IP"
$lMode.Controls.AddRange(@($rbLAuto,$rbLWifi,$rbLIp))

$lIp = New-Object System.Windows.Forms.TextBox
$lIpWifi = New-Object System.Windows.Forms.TextBox; $lIpWifi.Text = "192.168.1.127"
$lUser = New-Object System.Windows.Forms.TextBox; $lUser.Text = "device"
$lPass = New-Object System.Windows.Forms.TextBox; $lPass.Text = "meeting"; $lPass.UseSystemPasswordChar = $true
$lDeviceKey = New-Object System.Windows.Forms.TextBox
$lToken = New-Object System.Windows.Forms.TextBox; $lToken.UseSystemPasswordChar = $true
$lApiUrl = New-Object System.Windows.Forms.TextBox
$lCfgFile = New-Object System.Windows.Forms.TextBox; $lCfgFile.Text = $paths.MeetingConfig
$lOutDir = New-Object System.Windows.Forms.TextBox
$btnLOut = New-Object System.Windows.Forms.Button; $btnLOut.Text = "Choisir..."; $btnLOut.Width = 90

New-Row -Table $lLayout -Label "Tool" -Control $lTool
New-Row -Table $lLayout -Label "Service (opt)" -Control $lService
New-Row -Table $lLayout -Label "Lines" -Control $lLines
New-Row -Table $lLayout -Label "Follow" -Control $lFollow
New-Row -Table $lLayout -Label "Mode" -Control $lMode
New-Row -Table $lLayout -Label "IP (mode IP)" -Control $lIp
New-Row -Table $lLayout -Label "IP WiFi" -Control $lIpWifi
New-Row -Table $lLayout -Label "User" -Control $lUser
New-Row -Table $lLayout -Label "Password" -Control $lPass

$lLayout.Controls.Add((New-SectionHeader "Meeting overrides (option)"), 0, $lLayout.RowCount)
$lLayout.SetColumnSpan($lLayout.Controls[$lLayout.Controls.Count-1], 2)
$lLayout.RowCount += 1
[void]$lLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

New-Row -Table $lLayout -Label "DeviceKey" -Control $lDeviceKey
New-Row -Table $lLayout -Label "Token" -Control $lToken
New-Row -Table $lLayout -Label "ApiUrl" -Control $lApiUrl
New-Row -Table $lLayout -Label "ConfigFile" -Control $lCfgFile

$outPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$outPanel.Dock = "Top"
$outPanel.WrapContents = $false
$lOutDir.Width = 240
$outPanel.Controls.AddRange(@($lOutDir,$btnLOut))

$row = $lLayout.RowCount
$lLayout.RowCount = $row + 1
[void]$lLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
$lblOut = New-Object System.Windows.Forms.Label; $lblOut.Text = "OutputDir (collect)"; $lblOut.AutoSize = $true; $lblOut.Margin = "3,6,6,6"
$lLayout.Controls.Add($lblOut, 0, $row)
$lLayout.Controls.Add($outPanel, 1, $row)

$btnLOut.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $lOutDir.Text = $dlg.SelectedPath }
})

# Tab: Config
$tabConfig = New-Object System.Windows.Forms.TabPage
$tabConfig.Text = "Config"
$tabs.TabPages.Add($tabConfig) | Out-Null

$cLayout = New-Object System.Windows.Forms.TableLayoutPanel
$cLayout.Dock = "Fill"
$cLayout.ColumnCount = 2
$cLayout.RowCount = 0
[void]$cLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$cLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabConfig.Controls.Add($cLayout)

$cLayout.Controls.Add((New-SectionHeader "config_tool.ps1"), 0, 0)
$cLayout.SetColumnSpan($cLayout.Controls[$cLayout.Controls.Count-1], 2)
$cLayout.RowCount = 1
[void]$cLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$cAction = New-Object System.Windows.Forms.ComboBox
$cAction.DropDownStyle = "DropDownList"
$cAction.Items.AddRange(@("list","get","set","unset","show-files","export","import"))
$cAction.SelectedItem = "list"

$cFile = New-Object System.Windows.Forms.TextBox
$cFile.Text = "/etc/rpi-cam/config.env"

$cKey = New-Object System.Windows.Forms.TextBox
$cValue = New-Object System.Windows.Forms.TextBox
$cJsonPath = New-Object System.Windows.Forms.TextBox

$cInput = New-Object System.Windows.Forms.TextBox
$cOutput = New-Object System.Windows.Forms.TextBox
$btnCInput = New-Object System.Windows.Forms.Button; $btnCInput.Text = "Input..."; $btnCInput.Width = 90
$btnCOutput = New-Object System.Windows.Forms.Button; $btnCOutput.Text = "Output..."; $btnCOutput.Width = 90

$cInputPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$cInputPanel.Dock = "Top"
$cInputPanel.WrapContents = $false
$cInput.Width = 240
$cInputPanel.Controls.AddRange(@($cInput,$btnCInput))

$cOutputPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$cOutputPanel.Dock = "Top"
$cOutputPanel.WrapContents = $false
$cOutput.Width = 240
$cOutputPanel.Controls.AddRange(@($cOutput,$btnCOutput))

$cActionsPanel = New-Object System.Windows.Forms.FlowLayoutPanel
$cActionsPanel.Dock = "Top"
$cActionsPanel.WrapContents = $false
$btnCFetch = New-Object System.Windows.Forms.Button; $btnCFetch.Text = "Récupérer paramètres"; $btnCFetch.Width = 170
$cActionsPanel.Controls.Add($btnCFetch)

$cRestart = New-Object System.Windows.Forms.CheckBox; $cRestart.Text = "RestartServices"
$cServices = New-Object System.Windows.Forms.TextBox; $cServices.Text = "rpi-cam-webmanager"

$cMode = New-Object System.Windows.Forms.FlowLayoutPanel; $cMode.Dock = "Top"
$rbCAuto = New-Object System.Windows.Forms.RadioButton; $rbCAuto.Text = "Auto (Meeting)"; $rbCAuto.Checked = $true
$rbCWifi = New-Object System.Windows.Forms.RadioButton; $rbCWifi.Text = "WiFi"
$rbCIp = New-Object System.Windows.Forms.RadioButton; $rbCIp.Text = "IP"
$cMode.Controls.AddRange(@($rbCAuto,$rbCWifi,$rbCIp))

$cIp = New-Object System.Windows.Forms.TextBox
$cIpWifi = New-Object System.Windows.Forms.TextBox; $cIpWifi.Text = "192.168.1.127"
$cUser = New-Object System.Windows.Forms.TextBox; $cUser.Text = "device"
$cPass = New-Object System.Windows.Forms.TextBox; $cPass.Text = "meeting"; $cPass.UseSystemPasswordChar = $true

$cDeviceKey = New-Object System.Windows.Forms.TextBox
$cToken = New-Object System.Windows.Forms.TextBox; $cToken.UseSystemPasswordChar = $true
$cApiUrl = New-Object System.Windows.Forms.TextBox
$cCfgFile = New-Object System.Windows.Forms.TextBox; $cCfgFile.Text = $paths.MeetingConfig

New-Row -Table $cLayout -Label "Action" -Control $cAction
New-Row -Table $cLayout -Label "File" -Control $cFile
New-Row -Table $cLayout -Label "Key (env)" -Control $cKey
New-Row -Table $cLayout -Label "Value" -Control $cValue
New-Row -Table $cLayout -Label "JsonPath" -Control $cJsonPath
New-Row -Table $cLayout -Label "InputFile" -Control $cInputPanel
New-Row -Table $cLayout -Label "OutputFile" -Control $cOutputPanel
New-Row -Table $cLayout -Label "Actions" -Control $cActionsPanel
New-Row -Table $cLayout -Label "Restart" -Control $cRestart
New-Row -Table $cLayout -Label "Services" -Control $cServices
New-Row -Table $cLayout -Label "Mode" -Control $cMode
New-Row -Table $cLayout -Label "IP (mode IP)" -Control $cIp
New-Row -Table $cLayout -Label "IP WiFi" -Control $cIpWifi
New-Row -Table $cLayout -Label "User" -Control $cUser
New-Row -Table $cLayout -Label "Password" -Control $cPass

$cLayout.Controls.Add((New-SectionHeader "Meeting overrides (option)"), 0, $cLayout.RowCount)
$cLayout.SetColumnSpan($cLayout.Controls[$cLayout.Controls.Count-1], 2)
$cLayout.RowCount += 1
[void]$cLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

New-Row -Table $cLayout -Label "DeviceKey" -Control $cDeviceKey
New-Row -Table $cLayout -Label "Token" -Control $cToken
New-Row -Table $cLayout -Label "ApiUrl" -Control $cApiUrl
New-Row -Table $cLayout -Label "ConfigFile" -Control $cCfgFile

$btnCInput.Add_Click({
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $cInput.Text = $dlg.FileName }
})
$btnCOutput.Add_Click({
    $dlg = New-Object System.Windows.Forms.SaveFileDialog
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $cOutput.Text = $dlg.FileName }
})

function Build-ConfigInvocation {
    param([string]$ActionOverride)

    $actionToUse = if ($ActionOverride) { $ActionOverride } else { [string]$cAction.SelectedItem }
    $args = New-Object System.Collections.Generic.List[string]
    [void]$args.Add("-Action"); [void]$args.Add($actionToUse)
    if ($cFile.Text.Trim()) { [void]$args.Add("-File"); [void]$args.Add($cFile.Text.Trim()) }
    if ($cKey.Text.Trim()) { [void]$args.Add("-Key"); [void]$args.Add($cKey.Text.Trim()) }
    if ($cValue.Text) { [void]$args.Add("-Value"); [void]$args.Add($cValue.Text) }
    if ($cJsonPath.Text.Trim()) { [void]$args.Add("-JsonPath"); [void]$args.Add($cJsonPath.Text.Trim()) }

    if ($actionToUse -eq "export") {
        if (-not $cOutput.Text.Trim()) { throw "config_tool: OutputFile requis pour Action=export." }
        [void]$args.Add("-OutputFile"); [void]$args.Add($cOutput.Text.Trim())
    }
    if ($actionToUse -eq "import") {
        if (-not $cInput.Text.Trim()) { throw "config_tool: InputFile requis pour Action=import." }
        [void]$args.Add("-InputFile"); [void]$args.Add($cInput.Text.Trim())
    }

    if ($rbCIp.Checked) {
        if (-not $cIp.Text.Trim()) { throw "config_tool: IP requis en mode IP." }
        [void]$args.Add("-IP"); [void]$args.Add($cIp.Text.Trim())
    } elseif ($rbCWifi.Checked) {
        [void]$args.Add("-UseWifi")
        if ($cIpWifi.Text.Trim()) { [void]$args.Add("-IpWifi"); [void]$args.Add($cIpWifi.Text.Trim()) }
    } else {
        [void]$args.Add("-Auto")
    }

    if ($cUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($cUser.Text.Trim()) }
    if ($cPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($cPass.Text) }

    if ($cDeviceKey.Text.Trim()) { [void]$args.Add("-DeviceKey"); [void]$args.Add($cDeviceKey.Text.Trim()) }
    if ($cToken.Text) { [void]$args.Add("-Token"); [void]$args.Add($cToken.Text) }
    if ($cApiUrl.Text.Trim()) { [void]$args.Add("-ApiUrl"); [void]$args.Add($cApiUrl.Text.Trim()) }
    if ($cCfgFile.Text.Trim()) { [void]$args.Add("-MeetingConfigFile"); [void]$args.Add($cCfgFile.Text.Trim()) }

    if ($cRestart.Checked) { [void]$args.Add("-RestartServices") }
    if ($cServices.Text.Trim()) {
        $svc = $cServices.Text.Trim().Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        foreach ($s in $svc) {
            [void]$args.Add("-Services"); [void]$args.Add($s)
        }
    }

    return (Build-EncodedScriptInvocation -ScriptPath $paths.ConfigTool -ScriptArgs $args.ToArray())
}

$btnCFetch.Add_Click({
    try {
        $args = Build-ConfigInvocation -ActionOverride "list"
        if ($args) {
            $cmdBox.Text = "powershell $args"
            Start-LoggedProcess -Title "config_tool.ps1 (list)" -Arguments $args
        }
    } catch {
        Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
    }
})

# Tab: Stop services
$tabStop = New-Object System.Windows.Forms.TabPage
$tabStop.Text = "Stop services"
$tabs.TabPages.Add($tabStop) | Out-Null

$stLayout = New-Object System.Windows.Forms.TableLayoutPanel
$stLayout.Dock = "Fill"
$stLayout.ColumnCount = 2
$stLayout.RowCount = 0
[void]$stLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
[void]$stLayout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
$tabStop.Controls.Add($stLayout)

$stLayout.Controls.Add((New-SectionHeader "stop_services.sh (via deploy_scp + run_remote)"), 0, 0)
$stLayout.SetColumnSpan($stLayout.Controls[$stLayout.Controls.Count-1], 2)
$stLayout.RowCount = 1
[void]$stLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))

$stMode = New-Object System.Windows.Forms.FlowLayoutPanel; $stMode.Dock = "Top"
$rbStAuto = New-Object System.Windows.Forms.RadioButton; $rbStAuto.Text = "Auto (Meeting)"; $rbStAuto.Checked = $true
$rbStWifi = New-Object System.Windows.Forms.RadioButton; $rbStWifi.Text = "WiFi"
$rbStIp = New-Object System.Windows.Forms.RadioButton; $rbStIp.Text = "IP"
$stMode.Controls.AddRange(@($rbStAuto,$rbStWifi,$rbStIp))
$stIp = New-Object System.Windows.Forms.TextBox

$stBtns = New-Object System.Windows.Forms.FlowLayoutPanel; $stBtns.Dock = "Top"; $stBtns.WrapContents = $true
$btnStDeploy = New-Object System.Windows.Forms.Button; $btnStDeploy.Text = "Déployer /tmp/stop_services.sh"; $btnStDeploy.Width = 220
$btnStStop = New-Object System.Windows.Forms.Button; $btnStStop.Text = "Stop"; $btnStStop.Width = 90
$btnStStart = New-Object System.Windows.Forms.Button; $btnStStart.Text = "Start"; $btnStStart.Width = 90
$btnStRestart = New-Object System.Windows.Forms.Button; $btnStRestart.Text = "Restart"; $btnStRestart.Width = 90
$btnStStatus = New-Object System.Windows.Forms.Button; $btnStStatus.Text = "Status"; $btnStStatus.Width = 90
$stBtns.Controls.AddRange(@($btnStDeploy,$btnStStop,$btnStStart,$btnStRestart,$btnStStatus))

New-Row -Table $stLayout -Label "Mode" -Control $stMode
New-Row -Table $stLayout -Label "IP (mode IP)" -Control $stIp
New-Row -Table $stLayout -Label "Actions" -Control $stBtns

function Invoke-StopServicesAction([string]$action) {
    if ($action -eq "deploy") {
        if (-not (Test-Path -LiteralPath $paths.StopServices)) { throw "stop_services.sh introuvable: $($paths.StopServices)" }
        $scpArgs = New-Object System.Collections.Generic.List[string]
        [void]$scpArgs.Add("-Source"); [void]$scpArgs.Add($paths.StopServices)
        [void]$scpArgs.Add("-Dest"); [void]$scpArgs.Add("/tmp/")
        if ($rbStAuto.Checked) { [void]$scpArgs.Add("-Auto") }
        elseif ($rbStWifi.Checked) { [void]$scpArgs.Add("-UseWifi") }
        elseif ($rbStIp.Checked) {
            if (-not $stIp.Text.Trim()) { throw "IP requis en mode IP." }
            [void]$scpArgs.Add("-IpEthernet"); [void]$scpArgs.Add($stIp.Text.Trim())
        }
        $args = Build-EncodedScriptInvocation -ScriptPath $paths.DeployScp -ScriptArgs $scpArgs.ToArray()
        $cmdBox.Text = "powershell $args"
        Start-LoggedProcess -Title "deploy stop_services.sh" -Arguments $args
        return
    }

    $cmd = switch ($action) {
        "stop" { "sudo /tmp/stop_services.sh" }
        "start" { "sudo /tmp/stop_services.sh --start" }
        "restart" { "sudo /tmp/stop_services.sh --restart" }
        "status" { "sudo /tmp/stop_services.sh --status" }
        default { throw "Action invalide: $action" }
    }

    $runArgs = New-Object System.Collections.Generic.List[string]
    [void]$runArgs.Add($cmd)
    if ($rbStAuto.Checked) { [void]$runArgs.Add("-Auto") }
    elseif ($rbStWifi.Checked) { [void]$runArgs.Add("-Wifi") }
    elseif ($rbStIp.Checked) {
        if (-not $stIp.Text.Trim()) { throw "IP requis en mode IP." }
        [void]$runArgs.Add("-IP"); [void]$runArgs.Add($stIp.Text.Trim())
    }

    $args = Build-EncodedScriptInvocation -ScriptPath $paths.RunRemote -ScriptArgs $runArgs.ToArray()
    $cmdBox.Text = "powershell $args"
    Start-LoggedProcess -Title "stop_services.sh ($action)" -Arguments $args
}

$btnStDeploy.Add_Click({ try { Invoke-StopServicesAction "deploy" } catch { Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine) } })
$btnStStop.Add_Click({ try { Invoke-StopServicesAction "stop" } catch { Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine) } })
$btnStStart.Add_Click({ try { Invoke-StopServicesAction "start" } catch { Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine) } })
$btnStRestart.Add_Click({ try { Invoke-StopServicesAction "restart" } catch { Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine) } })
$btnStStatus.Add_Click({ try { Invoke-StopServicesAction "status" } catch { Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine) } })

# -----------------------------------------------------------------------------
# Device context + memory
# -----------------------------------------------------------------------------

$script:CurrentDeviceKey = $null
$script:CurrentDeviceIp = $null

function Get-OnlineLabel {
    param([object]$Response)
    if ($null -eq $Response) { return "unknown" }
    $valOnline = Get-MeetingField -Object $Response -Name "online"
    if ($valOnline -ne $null) { return ($valOnline ? "online" : "offline") }
    $valIsOnline = Get-MeetingField -Object $Response -Name "is_online"
    if ($valIsOnline -ne $null) { return ($valIsOnline ? "online" : "offline") }
    $valStatus = Get-MeetingField -Object $Response -Name "status"
    if ($valStatus) {
        $s = [string]$valStatus
        if ($s -match "online") { return "online" }
        if ($s -match "offline") { return "offline" }
    }
    return "unknown"
}

function Refresh-DeviceMemoryList {
    $memList.Items.Clear()
    $entries = Load-DeviceMemory
    foreach ($e in $entries) {
        $deviceKey = if ($e.PSObject.Properties.Match('device_key')) { [string]$e.device_key } else { "" }
        $ip = if ($e.PSObject.Properties.Match('ip')) { [string]$e.ip } else { "" }
        $online = if ($e.PSObject.Properties.Match('online')) { [string]$e.online } else { "" }
        $lastSeen = if ($e.PSObject.Properties.Match('last_seen')) { [string]$e.last_seen } else { "" }
        $item = New-Object System.Windows.Forms.ListViewItem($deviceKey)
        [void]$item.SubItems.Add($ip)
        [void]$item.SubItems.Add($online)
        [void]$item.SubItems.Add($lastSeen)
        $memList.Items.Add($item) | Out-Null
    }
}

function Apply-DeviceContext {
    param([string]$DeviceKey,[string]$DeviceIp)
    if ($DeviceKey) { $script:CurrentDeviceKey = $DeviceKey }
    if ($DeviceIp) { $script:CurrentDeviceIp = $DeviceIp }

    if ($mKey) { $mKey.Text = $script:CurrentDeviceKey }
    if ($mIp) { $mIp.Text = $script:CurrentDeviceIp }
    if ($iIp) { $iIp.Text = $script:CurrentDeviceIp }
    if ($rIp) { $rIp.Text = $script:CurrentDeviceIp }
    if ($sIpEth) { $sIpEth.Text = $script:CurrentDeviceIp }
    if ($shIpEth) { $shIpEth.Text = $script:CurrentDeviceIp }
    if ($lIp) { $lIp.Text = $script:CurrentDeviceIp }
    if ($cIp) { $cIp.Text = $script:CurrentDeviceIp }
    if ($stIp) { $stIp.Text = $script:CurrentDeviceIp }

    if ($lDeviceKey) { $lDeviceKey.Text = $script:CurrentDeviceKey }
    if ($cDeviceKey) { $cDeviceKey.Text = $script:CurrentDeviceKey }
    if ($uDeviceKey) { $uDeviceKey.Text = $script:CurrentDeviceKey }
    if ($uIp) { $uIp.Text = $script:CurrentDeviceIp }
}

$btnMemUse.Add_Click({
    if ($memList.SelectedItems.Count -eq 0) { return }
    $sel = $memList.SelectedItems[0]
    $dk = $sel.SubItems[0].Text
    $ip = $sel.SubItems[1].Text
    Apply-DeviceContext -DeviceKey $dk -DeviceIp $ip
})

$btnMemSave.Add_Click({
    $dk = $mKey.Text.Trim()
    $ip = $mIp.Text.Trim()
    if (-not $dk -and -not $ip) { return }
    Upsert-DeviceMemory -DeviceKey $dk -Ip $ip -Online "" | Out-Null
    Refresh-DeviceMemoryList
})

$btnMemRemove.Add_Click({
    if ($memList.SelectedItems.Count -eq 0) { return }
    $sel = $memList.SelectedItems[0]
    $dk = $sel.SubItems[0].Text
    $ip = $sel.SubItems[1].Text
    $entries = Load-DeviceMemory | Where-Object {
        $entryKey = if ($_.PSObject.Properties.Match('device_key')) { $_.device_key } else { "" }
        $entryIp = if ($_.PSObject.Properties.Match('ip')) { $_.ip } else { "" }
        if ($dk) { $entryKey -ne $dk } else { $entryIp -ne $ip }
    }
    Save-DeviceMemory -Entries $entries
    Refresh-DeviceMemoryList
})

    $btnMemRefresh.Add_Click({
    $cfg = Load-MeetingConfig
    if (-not $cfg.api_url) {
        Append-TextSafely -textBox $logBox -text ("[Meeting] API URL manquante pour refresh status." + [Environment]::NewLine)
        return
    }
    $entries = Load-DeviceMemory
    foreach ($e in $entries) {
        if (-not $e.device_key) { continue }
        $resp = Invoke-MeetingDeviceLookup -DeviceKey $e.device_key -ApiUrl $cfg.api_url -TokenCode $cfg.token_code
        if ($resp) {
            $respIp = Get-MeetingField -Object $resp -Name "ip_address"
            if (-not $respIp) { $respIp = Get-MeetingField -Object $resp -Name "ip" }
            if ($respIp) { $e.ip = [string]$respIp }
            $e.online = Get-OnlineLabel -Response $resp
            $e.last_seen = (Get-Date).ToString("s")
        }
    }
    Save-DeviceMemory -Entries $entries
    Refresh-DeviceMemoryList
})

Refresh-DeviceMemoryList

# -----------------------------------------------------------------------------
# Startup assistant
# -----------------------------------------------------------------------------

function Show-DeviceAssistant {
    $dlg = New-Object System.Windows.Forms.Form
    $dlg.Text = "RTSP-Full — Assistant"
    $dlg.StartPosition = "CenterParent"
    $dlg.Size = New-Object System.Drawing.Size(520, 320)
    $dlg.MinimumSize = New-Object System.Drawing.Size(520, 320)
    $dlg.Font = New-Object System.Drawing.Font("Segoe UI", 9)

    $layout = New-Object System.Windows.Forms.TableLayoutPanel
    $layout.Dock = "Fill"
    $layout.ColumnCount = 2
    $layout.RowCount = 0
    [void]$layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 140)))
    [void]$layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    $dlg.Controls.Add($layout)

    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = "Saisir une DeviceKey (Meeting) ou une IP."
    $lbl.AutoSize = $true
    $row = $layout.RowCount
    $layout.RowCount = $row + 1
    [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
    $layout.Controls.Add($lbl, 0, $row)
    $layout.SetColumnSpan($lbl, 2)

    $dkText = New-Object System.Windows.Forms.TextBox
    $ipText = New-Object System.Windows.Forms.TextBox
    $tokenText = New-Object System.Windows.Forms.TextBox
    $tokenText.UseSystemPasswordChar = $true

    New-Row -Table $layout -Label "DeviceKey" -Control $dkText
    New-Row -Table $layout -Label "Token (opt)" -Control $tokenText
    New-Row -Table $layout -Label "IP" -Control $ipText

    $statusLabel = New-Object System.Windows.Forms.Label
    $statusLabel.AutoSize = $true
    $statusLabel.ForeColor = [System.Drawing.Color]::DimGray
    $row = $layout.RowCount
    $layout.RowCount = $row + 1
    [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
    $layout.Controls.Add($statusLabel, 0, $row)
    $layout.SetColumnSpan($statusLabel, 2)

    $btns = New-Object System.Windows.Forms.FlowLayoutPanel
    $btns.Dock = "Top"
    $btns.WrapContents = $false
    $btnLookup = New-Object System.Windows.Forms.Button; $btnLookup.Text = "Lookup Meeting"; $btnLookup.Width = 130
    $btnOk = New-Object System.Windows.Forms.Button; $btnOk.Text = "Continuer"; $btnOk.Width = 110
    $btnCancel = New-Object System.Windows.Forms.Button; $btnCancel.Text = "Annuler"; $btnCancel.Width = 110
    $btns.Controls.AddRange(@($btnLookup,$btnOk,$btnCancel))

    $row = $layout.RowCount
    $layout.RowCount = $row + 1
    [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
    $layout.Controls.Add($btns, 0, $row)
    $layout.SetColumnSpan($btns, 2)

    $lastResp = $null

    $btnLookup.Add_Click({
        $cfg = Load-MeetingConfig
        if (-not $cfg.api_url) {
            $statusLabel.Text = "Meeting config incomplet (API URL)."
            return
        }
        if (-not $dkText.Text.Trim()) {
            $statusLabel.Text = "DeviceKey requise pour lookup."
            return
        }
        $token = if ($tokenText.Text) { $tokenText.Text } else { $cfg.token_code }
        $resp = Invoke-MeetingDeviceLookup -DeviceKey $dkText.Text.Trim() -ApiUrl $cfg.api_url -TokenCode $token
        if ($resp) {
            $lastResp = $resp
            $respIp = Get-MeetingField -Object $resp -Name "ip_address"
            if (-not $respIp) { $respIp = Get-MeetingField -Object $resp -Name "ip" }
            if ($respIp) { $ipText.Text = [string]$respIp }
            $statusLabel.Text = "Meeting: " + (Get-OnlineLabel -Response $resp)
        } else {
            $statusLabel.Text = "Lookup Meeting échoué."
        }
    })

    $btnOk.Add_Click({
        $dk = $dkText.Text.Trim()
        $ip = $ipText.Text.Trim()
        if (-not $dk -and -not $ip) {
            $statusLabel.Text = "DeviceKey ou IP requis."
            return
        }
        if (-not $ip) {
            $cfg = Load-MeetingConfig
            $token = if ($tokenText.Text) { $tokenText.Text } else { $cfg.token_code }
            $resp = Invoke-MeetingDeviceLookup -DeviceKey $dk -ApiUrl $cfg.api_url -TokenCode $token
            $respIp = $null
            if ($resp) {
                $respIp = Get-MeetingField -Object $resp -Name "ip_address"
                if (-not $respIp) { $respIp = Get-MeetingField -Object $resp -Name "ip" }
            }
            if ($respIp) {
                $ip = [string]$respIp
                $lastResp = $resp
            }
        }
        if (-not $ip) {
            $statusLabel.Text = "IP requise si DeviceKey indisponible."
            return
        }
        $dlg.Tag = @{ DeviceKey = $dk; Ip = $ip; Online = (Get-OnlineLabel -Response $lastResp) }
        $dlg.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $dlg.Close()
    })

    $btnCancel.Add_Click({
        $dlg.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
        $dlg.Close()
    })

    $cfgInit = Load-MeetingConfig
    if ($cfgInit.device_key) { $dkText.Text = $cfgInit.device_key }
    if ($cfgInit.token_code) { $tokenText.Text = $cfgInit.token_code }

    $dlg.ShowDialog($form) | Out-Null
    return $dlg.Tag
}

# -----------------------------------------------------------------------------
# Invocation builder + buttons
# -----------------------------------------------------------------------------

function Get-InvocationForActiveTab {
    switch ($tabs.SelectedTab.Text) {
        "Install" {
            $args = New-Object System.Collections.Generic.List[string]
            if ($iIp.Text.Trim()) { [void]$args.Add("-IP"); [void]$args.Add($iIp.Text.Trim()) }
            if ($cbICheckOnly.Checked) { [void]$args.Add("-CheckOnly") }
            if ($cbISkipInstall.Checked) { [void]$args.Add("-SkipInstall") }
            if ($cbIMonitor.Checked) { [void]$args.Add("-Monitor") }
            if ($cbINoProvision.Checked) { [void]$args.Add("-NoProvision") }
            if ($cbINoReboot.Checked) { [void]$args.Add("-NoReboot") }
            if ($cbINoBurnToken.Checked) { [void]$args.Add("-NoBurnToken") }

            if ($iTz.Text.Trim()) { [void]$args.Add("-Timezone"); [void]$args.Add($iTz.Text.Trim()) }
            if ($iUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($iUser.Text.Trim()) }
            if ($iPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($iPass.Text) }
            if ([int]$iTimeout.Value -gt 0) { [void]$args.Add("-Timeout"); [void]$args.Add([string]([int]$iTimeout.Value)) }
            if ($iKey.Text.Trim()) { [void]$args.Add("-DeviceKey"); [void]$args.Add($iKey.Text.Trim()) }
            if ($iToken.Text) { [void]$args.Add("-Token"); [void]$args.Add($iToken.Text) }
            if ($iUrl.Text.Trim()) { [void]$args.Add("-MeetingApiUrl"); [void]$args.Add($iUrl.Text.Trim()) }

            return @{
                Title = "install_device.ps1"
                Arguments = (Build-EncodedScriptInvocation -ScriptPath $paths.InstallDevice -ScriptArgs $args.ToArray())
            }
        }

        "Run remote" {
            if (-not $rCmd.Text.Trim()) { throw "run_remote: champ 'Commande' requis." }
            $args = New-Object System.Collections.Generic.List[string]
            [void]$args.Add($rCmd.Text.Trim())
            if ($rbRAuto.Checked) { [void]$args.Add("-Auto") }
            elseif ($rbRWifi.Checked) { [void]$args.Add("-Wifi") }
            elseif ($rbRIp.Checked) {
                if (-not $rIp.Text.Trim()) { throw "run_remote: IP requis en mode IP." }
                [void]$args.Add("-IP"); [void]$args.Add($rIp.Text.Trim())
            }
            if ([int]$rTimeout.Value -gt 0) { [void]$args.Add("-Timeout"); [void]$args.Add([string]([int]$rTimeout.Value)) }

            return @{
                Title = "run_remote.ps1"
                Arguments = (Build-EncodedScriptInvocation -ScriptPath $paths.RunRemote -ScriptArgs $args.ToArray())
            }
        }

        "Deploy (SCP)" {
            if (-not $sSource.Text.Trim()) { throw "deploy_scp: Source requis." }
            if (-not $sDest.Text.Trim()) { throw "deploy_scp: Dest requis." }
            $args = New-Object System.Collections.Generic.List[string]
            [void]$args.Add("-Source"); [void]$args.Add($sSource.Text.Trim())
            [void]$args.Add("-Dest"); [void]$args.Add($sDest.Text.Trim())
            if ($cbSRec.Checked) { [void]$args.Add("-Recursive") }
            if ($cbSDry.Checked) { [void]$args.Add("-DryRun") }
            if ($cbSNoR.Checked) { [void]$args.Add("-NoRestart") }
            if ($rbSAuto.Checked) { [void]$args.Add("-Auto") }
            elseif ($rbSWifi.Checked) { [void]$args.Add("-UseWifi") }
            if ($sUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($sUser.Text.Trim()) }
            if ($sPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($sPass.Text) }
            if ($sIpEth.Text.Trim()) { [void]$args.Add("-IpEthernet"); [void]$args.Add($sIpEth.Text.Trim()) }
            if ($sIpWifi.Text.Trim()) { [void]$args.Add("-IpWifi"); [void]$args.Add($sIpWifi.Text.Trim()) }

            return @{
                Title = "deploy_scp.ps1"
                Arguments = (Build-EncodedScriptInvocation -ScriptPath $paths.DeployScp -ScriptArgs $args.ToArray())
            }
        }

        "Update" {
            $hasIp = $uIp.Text.Trim()
            $hasKey = $uDeviceKey.Text.Trim()
            if (-not $hasIp -and -not $hasKey -and -not $uFallback.Text.Trim()) {
                throw "update_device: IP, DeviceKey ou Fallback IP requis."
            }
            $args = New-Object System.Collections.Generic.List[string]
            if ($hasIp) { [void]$args.Add("-IP"); [void]$args.Add($uIp.Text.Trim()) }
            if ($hasKey) { [void]$args.Add("-DeviceKey"); [void]$args.Add($uDeviceKey.Text.Trim()) }
            if ($uToken.Text) { [void]$args.Add("-Token"); [void]$args.Add($uToken.Text) }
            if ($uApiUrl.Text.Trim()) { [void]$args.Add("-ApiUrl"); [void]$args.Add($uApiUrl.Text.Trim()) }
            if ($cbUDry.Checked) { [void]$args.Add("-DryRun") }
            if ($cbUNoRestart.Checked) { [void]$args.Add("-NoRestart") }
            if ($uUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($uUser.Text.Trim()) }
            if ($uPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($uPass.Text) }
            if ($uFallback.Text.Trim()) { [void]$args.Add("-FallbackIP"); [void]$args.Add($uFallback.Text.Trim()) }

            return @{
                Title = "update_device.ps1"
                Arguments = (Build-EncodedScriptInvocation -ScriptPath $paths.UpdateDevice -ScriptArgs $args.ToArray())
            }
        }

        "SSH" {
            $args = New-Object System.Collections.Generic.List[string]
            if ($shCmd.Text.Trim()) { [void]$args.Add("-Command"); [void]$args.Add($shCmd.Text.Trim()) }
            if ($shUseWifi.Checked) { [void]$args.Add("-UseWifi") }
            if ($shUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($shUser.Text.Trim()) }
            if ($shPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($shPass.Text) }
            if ($shIpEth.Text.Trim()) { [void]$args.Add("-IpEthernet"); [void]$args.Add($shIpEth.Text.Trim()) }
            if ($shIpWifi.Text.Trim()) { [void]$args.Add("-IpWifi"); [void]$args.Add($shIpWifi.Text.Trim()) }

            return @{
                Title = "ssh_device.ps1"
                Arguments = (Build-EncodedScriptInvocation -ScriptPath $paths.SshDevice -ScriptArgs $args.ToArray())
            }
        }

        "Logs/Diag" {
            $args = New-Object System.Collections.Generic.List[string]
            [void]$args.Add("-Tool"); [void]$args.Add([string]$lTool.SelectedItem)
            if ($lService.Text.Trim()) { [void]$args.Add("-Service"); [void]$args.Add($lService.Text.Trim()) }
            [void]$args.Add("-Lines"); [void]$args.Add([string]([int]$lLines.Value))
            if ($lFollow.Checked) { [void]$args.Add("-Follow") }

            if ($rbLIp.Checked) {
                if (-not $lIp.Text.Trim()) { throw "get_logs: IP requis en mode IP." }
                [void]$args.Add("-IP"); [void]$args.Add($lIp.Text.Trim())
            } elseif ($rbLWifi.Checked) {
                [void]$args.Add("-UseWifi")
                if ($lIpWifi.Text.Trim()) { [void]$args.Add("-IpWifi"); [void]$args.Add($lIpWifi.Text.Trim()) }
            } else {
                [void]$args.Add("-Auto")
            }

            if ($lUser.Text.Trim()) { [void]$args.Add("-User"); [void]$args.Add($lUser.Text.Trim()) }
            if ($lPass.Text) { [void]$args.Add("-Password"); [void]$args.Add($lPass.Text) }

            if ($lDeviceKey.Text.Trim()) { [void]$args.Add("-DeviceKey"); [void]$args.Add($lDeviceKey.Text.Trim()) }
            if ($lToken.Text) { [void]$args.Add("-Token"); [void]$args.Add($lToken.Text) }
            if ($lApiUrl.Text.Trim()) { [void]$args.Add("-ApiUrl"); [void]$args.Add($lApiUrl.Text.Trim()) }
            if ($lCfgFile.Text.Trim()) { [void]$args.Add("-MeetingConfigFile"); [void]$args.Add($lCfgFile.Text.Trim()) }

            if ($lTool.SelectedItem -eq "collect") {
                if (-not $lOutDir.Text.Trim()) { throw "get_logs: OutputDir requis pour Tool=collect." }
                [void]$args.Add("-OutputDir"); [void]$args.Add($lOutDir.Text.Trim())
            }

            return @{
                Title = "get_logs.ps1"
                Arguments = (Build-EncodedScriptInvocation -ScriptPath $paths.GetLogs -ScriptArgs $args.ToArray())
            }
        }

        "Config" {
            return @{
                Title = "config_tool.ps1"
                Arguments = (Build-ConfigInvocation)
            }
        }
    }

    return @{ Title = "N/A"; Arguments = "" }
}

function Refresh-CommandPreview {
    $inv = Get-InvocationForActiveTab
    $script:CurrentInvocation = $inv
    if (-not $inv.Arguments) { $cmdBox.Text = ""; return }
    $cmdBox.Text = "powershell $($inv.Arguments)"
}

$tabs.Add_SelectedIndexChanged({ try { Refresh-CommandPreview } catch { } })

$btnBuild.Add_Click({
    try { Refresh-CommandPreview } catch { Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine) }
})
$btnCopy.Add_Click({ if ($cmdBox.Text) { [System.Windows.Forms.Clipboard]::SetText($cmdBox.Text) } })
$btnClear.Add_Click({ $logBox.Clear() })

$btnRun.Add_Click({
    try {
        Refresh-CommandPreview
        if (-not $script:CurrentInvocation -or -not $script:CurrentInvocation.Arguments) { throw "Aucune commande à exécuter pour cet onglet." }
        Start-LoggedProcess -Title $script:CurrentInvocation.Title -Arguments $script:CurrentInvocation.Arguments
    } catch {
        Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
        Set-RunningState $false
    }
})

$btnStop.Add_Click({
    try {
        if ($null -eq $process -or $process.HasExited) { return }
        Append-TextSafely -textBox $logBox -text ("`r`n[Stopping] kill process..." + [Environment]::NewLine)
        $process.Kill()
    } catch {
        Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
    }
})

$form.add_FormClosing({
    try { if ($null -ne $process -and -not $process.HasExited) { $process.Kill() } } catch { }
})

try {
    $assistantResult = Show-DeviceAssistant
    if (-not $assistantResult) { return }
    Apply-DeviceContext -DeviceKey $assistantResult.DeviceKey -DeviceIp $assistantResult.Ip
    Upsert-DeviceMemory -DeviceKey $assistantResult.DeviceKey -Ip $assistantResult.Ip -Online $assistantResult.Online | Out-Null
    Refresh-DeviceMemoryList
} catch {
    Append-TextSafely -textBox $logBox -text ("[ERREUR] " + $_.Exception.Message + [Environment]::NewLine)
}

try { Refresh-CommandPreview } catch { }
[void]$form.ShowDialog()
