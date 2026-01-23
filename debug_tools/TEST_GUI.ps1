<#
 TEST_GUI.ps1 - Minimal test GUI to debug process launching
#>

$ErrorActionPreference = "Stop"
$debugLog = "c:\Users\sn8k\Documents\gitHub\RTSP-Full\debug_tools\logs\test_gui_debug.log"

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss.fff')] $msg"
    Write-Host $line
    Add-Content -LiteralPath $debugLog -Value $line -ErrorAction SilentlyContinue
}

Log "=== TEST GUI STARTING ==="

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()
    
    Log "Assemblies loaded"
    
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Test GUI"
    $form.Size = New-Object System.Drawing.Size(600, 400)
    $form.StartPosition = "CenterScreen"
    
    $logBox = New-Object System.Windows.Forms.TextBox
    $logBox.Multiline = $true
    $logBox.Dock = "Fill"
    $logBox.ScrollBars = "Both"
    $form.Controls.Add($logBox)
    
    $btnPanel = New-Object System.Windows.Forms.Panel
    $btnPanel.Dock = "Bottom"
    $btnPanel.Height = 50
    $form.Controls.Add($btnPanel)
    
    $btnRun = New-Object System.Windows.Forms.Button
    $btnRun.Text = "Run Process"
    $btnRun.Location = New-Object System.Drawing.Point(10, 10)
    $btnRun.Width = 150
    $btnPanel.Controls.Add($btnRun)
    
    Log "Form created"
    
    $script:process = $null
    $scriptRoot = Split-Path -Parent $PSCommandPath
    $installerPath = Join-Path $scriptRoot "install_device.ps1"
    
    $btnRun.Add_Click({
        Log "Button clicked!"
        $logBox.AppendText("[Button clicked]`r`n")
        
        try {
            Log "Creating process..."
            $logBox.AppendText("[Creating process...]`r`n")
            
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = "powershell.exe"
            $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$installerPath`" -IP `"192.168.1.202`" -CheckOnly"
            $psi.UseShellExecute = $false
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError = $true
            $psi.CreateNoWindow = $true
            
            Log "PSI created: $($psi.Arguments)"
            
            $script:process = New-Object System.Diagnostics.Process
            $script:process.StartInfo = $psi
            $script:process.EnableRaisingEvents = $true
            
            # Use Register-ObjectEvent instead of add_OutputDataReceived
            $null = Register-ObjectEvent -InputObject $script:process -EventName OutputDataReceived -Action {
                $data = $Event.SourceEventArgs.Data
                if ($data) {
                    Add-Content -LiteralPath "c:\Users\sn8k\Documents\gitHub\RTSP-Full\debug_tools\logs\test_gui_debug.log" -Value "[OUT] $data" -ErrorAction SilentlyContinue
                }
            }
            
            $null = Register-ObjectEvent -InputObject $script:process -EventName ErrorDataReceived -Action {
                $data = $Event.SourceEventArgs.Data
                if ($data) {
                    Add-Content -LiteralPath "c:\Users\sn8k\Documents\gitHub\RTSP-Full\debug_tools\logs\test_gui_debug.log" -Value "[ERR] $data" -ErrorAction SilentlyContinue
                }
            }
            
            $null = Register-ObjectEvent -InputObject $script:process -EventName Exited -Action {
                Add-Content -LiteralPath "c:\Users\sn8k\Documents\gitHub\RTSP-Full\debug_tools\logs\test_gui_debug.log" -Value "[EXITED]" -ErrorAction SilentlyContinue
            }
            
            Log "Events registered"
            
            $started = $script:process.Start()
            Log "Started: $started, PID: $($script:process.Id)"
            $logBox.AppendText("[Process started PID: $($script:process.Id)]`r`n")
            
            $script:process.BeginOutputReadLine()
            $script:process.BeginErrorReadLine()
            
            Log "Reading started"
            $logBox.AppendText("[Reading output...]`r`n")
            
        } catch {
            $err = $_.Exception.Message
            Log "ERROR: $err"
            Log "Stack: $($_.ScriptStackTrace)"
            $logBox.AppendText("[ERROR] $err`r`n")
        }
    })
    
    Log "Showing form..."
    [void]$form.ShowDialog()
    Log "Form closed"
    
} catch {
    Log "FATAL: $($_.Exception.Message)"
    Log "Stack: $($_.ScriptStackTrace)"
}
