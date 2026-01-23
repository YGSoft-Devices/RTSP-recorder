# config_tool.ps1 - Modify project configuration on device (config.env + /etc/rpi-cam/*.json)
# Version: 1.0.0
#
# Usage examples:
#   .\debug_tools\config_tool.ps1 -Action list -File "/etc/rpi-cam/config.env"
#   .\debug_tools\config_tool.ps1 -Action get -File "/etc/rpi-cam/config.env" -Key "RTSP_PORT"
#   .\debug_tools\config_tool.ps1 -Action set -File "/etc/rpi-cam/config.env" -Key "RTSP_PORT" -Value "8554"
#   .\debug_tools\config_tool.ps1 -Action unset -File "/etc/rpi-cam/config.env" -Key "RTSP_PASSWORD"
#   .\debug_tools\config_tool.ps1 -Action list -File "/etc/rpi-cam/wifi_failover.json"
#   .\debug_tools\config_tool.ps1 -Action get -File "/etc/rpi-cam/wifi_failover.json" -JsonPath "backup_ssid"
#   .\debug_tools\config_tool.ps1 -Action set -File "/etc/rpi-cam/wifi_failover.json" -JsonPath "backup_ssid" -Value "MySSID"
#   .\debug_tools\config_tool.ps1 -Action export -File "/etc/rpi-cam/config.env" -OutputFile ".\\config.env"
#   .\debug_tools\config_tool.ps1 -Action import -File "/etc/rpi-cam/config.env" -InputFile ".\\config.env"
#
# IP / Meeting:
#   .\debug_tools\config_tool.ps1 -Auto
#   .\debug_tools\config_tool.ps1 -DeviceKey "XYZ" -Token "abc" -ApiUrl "https://meeting.ygsoft.fr/api" -Auto
#   .\debug_tools\config_tool.ps1 -IP "192.168.1.202"

param(
    [ValidateSet("list","get","set","unset","show-files","export","import")]
    [string]$Action = "list",

    [string]$File = "/etc/rpi-cam/config.env",
    [string]$Key,
    [string]$Value,
    [string]$JsonPath,

    [string]$InputFile,
    [string]$OutputFile,

    [switch]$RestartServices,
    [string[]]$Services = @("rpi-cam-webmanager"),

    [string]$IP,
    [switch]$UseWifi,
    [string]$IpWifi = "192.168.1.127",
    [switch]$Auto,

    [string]$DeviceKey,
    [string]$Token,
    [string]$ApiUrl,
    [string]$MeetingConfigFile,

    [string]$User = "device",
    [string]$Password = "meeting"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Escape-BashSingleQuotes {
    param([string]$Value)
    if ($null -eq $Value) { return "" }
    return ($Value -replace "'", "'\\''")
}

function Test-WslSshpass {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) { return $false }
    try {
        $check = wsl which sshpass 2>$null
        return [bool]$check
    } catch {
        return $false
    }
}

function Invoke-DeviceSsh {
    param(
        [Parameter(Mandatory=$true)][string]$DeviceIP,
        [Parameter(Mandatory=$true)][string]$Command,
        [int]$Timeout = 10
    )

    $sshOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=$Timeout"

    if (Test-WslSshpass) {
        $escapedCmd = Escape-BashSingleQuotes -Value $Command
        $wslCmd = "sshpass -p '$Password' ssh $sshOptions $User@$DeviceIP '$escapedCmd'"
        wsl bash -c $wslCmd
        return
    }

    $sshArgs = @(
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-o", "ConnectTimeout=$Timeout",
        "$User@$DeviceIP",
        $Command
    )
    & ssh @sshArgs
}

function Invoke-DeviceScp {
    param(
        [Parameter(Mandatory=$true)][string]$DeviceIP,
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [switch]$ToRemote
    )

    $scpOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

    if (Test-WslSshpass) {
        if ($ToRemote) {
            $wslSource = wsl wslpath -u "'$((Resolve-Path $Source).Path)'" 2>$null
            if (-not $wslSource) {
                $winPath = (Resolve-Path $Source).Path
                $wslSource = "/mnt/" + $winPath.Substring(0,1).ToLower() + $winPath.Substring(2).Replace('\', '/')
            }
            $scpCmd = "sshpass -p '$Password' scp $scpOptions $wslSource ${User}@${DeviceIP}:$Destination"
        } else {
            $localDir = Split-Path -Parent $Destination
            if (-not $localDir) { $localDir = "." }
            if (-not (Test-Path $localDir)) { New-Item -ItemType Directory -Path $localDir -Force | Out-Null }
            $wslLocalDir = wsl wslpath -u "'$((Resolve-Path $localDir).Path)'" 2>$null
            if (-not $wslLocalDir) {
                $winPath = (Resolve-Path $localDir).Path
                $wslLocalDir = "/mnt/" + $winPath.Substring(0,1).ToLower() + $winPath.Substring(2).Replace('\', '/')
            }
            $localName = Split-Path -Leaf $Destination
            $wslLocalPath = ($wslLocalDir.TrimEnd('/') + "/" + $localName) -replace '\\', '/'
            $scpCmd = "sshpass -p '$Password' scp $scpOptions ${User}@${DeviceIP}:$Source $wslLocalPath"
        }
        wsl bash -c $scpCmd
        return
    }

    if ($ToRemote) {
        & scp @($scpOptions.Split(' ')) $Source "${User}@${DeviceIP}:$Destination"
    } else {
        $localDir = Split-Path -Parent $Destination
        if ($localDir -and -not (Test-Path $localDir)) {
            New-Item -ItemType Directory -Path $localDir -Force | Out-Null
        }
        & scp @($scpOptions.Split(' ')) "${User}@${DeviceIP}:$Source" $Destination
    }
}

function Resolve-DeviceIP {
    $defaultEthIp = "192.168.1.202"
    $knownIPs = @("192.168.1.202","192.168.1.124","192.168.1.127")

    if ($IP) { return $IP }
    if ($UseWifi) { return $IpWifi }

    $shouldUseMeeting = $Auto -or [bool]$DeviceKey -or [bool]$Token -or [bool]$ApiUrl -or [bool]$MeetingConfigFile
    if (-not $shouldUseMeeting) { return $defaultEthIp }

    $getDeviceIPScript = Join-Path $PSScriptRoot "Get-DeviceIP.ps1"
    if (-not (Test-Path $getDeviceIPScript)) { return $defaultEthIp }

    . $getDeviceIPScript
    $resolved = Find-DeviceIP -Quiet -ApiUrl $ApiUrl -DeviceKey $DeviceKey -TokenCode $Token -ConfigFile $MeetingConfigFile -KnownIPs $knownIPs
    if ($resolved) { return $resolved }
    return $defaultEthIp
}

$DeviceIP = Resolve-DeviceIP
Write-Host "=== RTSP-Full Config Tool ===" -ForegroundColor Cyan
Write-Host "Action:   $Action" -ForegroundColor DarkGray
Write-Host "DeviceIP: $DeviceIP" -ForegroundColor DarkGray
Write-Host "File:     $File" -ForegroundColor DarkGray

if ($Action -in @("get","set","unset") -and -not $Key -and -not $JsonPath) {
    throw "Action '$Action' requires -Key (config.env) or -JsonPath (JSON)."
}

if ($Action -eq "export" -and -not $OutputFile) {
    throw "Action 'export' requires -OutputFile."
}
if ($Action -eq "import" -and -not $InputFile) {
    throw "Action 'import' requires -InputFile."
}

$pythonScript = @"
import os, sys, json, re, shutil, datetime

action = os.environ.get("ACTION", "list")
path = os.environ.get("CFG_FILE", "/etc/rpi-cam/config.env")
key = os.environ.get("KEY")
value = os.environ.get("VALUE", "")
json_path = os.environ.get("JSON_PATH")

def is_json_file(p):
    return p.endswith(".json")

def backup_file(p):
    if not os.path.exists(p):
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    dst = p + ".bak-" + ts
    shutil.copy2(p, dst)
    return dst

def load_env_lines(p):
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()

def write_env_lines(p, lines):
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(lines)

def format_env_value(v):
    escaped = v.replace('"', '\\"')
    return f'"{escaped}"'

def parse_env_value(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1].replace('\\"', '"')
    return s

def env_list(p):
    for line in load_env_lines(p):
        line = line.rstrip("\\n")
        if not line or line.strip().startswith("#"):
            continue
        print(line)

def env_get(p, k):
    pat = re.compile(r"^\\s*%s\\s*=" % re.escape(k))
    for line in load_env_lines(p):
        if pat.match(line):
            _, v = line.split("=", 1)
            print(parse_env_value(v))
            return
    sys.exit(2)

def env_set(p, k, v):
    lines = load_env_lines(p)
    pat = re.compile(r"^\\s*%s\\s*=" % re.escape(k))
    new_line = f"{k}={format_env_value(v)}\\n"
    found = False
    for i, line in enumerate(lines):
        if pat.match(line):
            lines[i] = new_line
            found = True
            break
    if not found:
        lines.append(new_line)
    bak = backup_file(p)
    write_env_lines(p, lines)
    if bak:
        print("backup:", bak)

def env_unset(p, k):
    lines = load_env_lines(p)
    pat = re.compile(r"^\\s*%s\\s*=" % re.escape(k))
    new_lines = [ln for ln in lines if not pat.match(ln)]
    bak = backup_file(p)
    write_env_lines(p, new_lines)
    if bak:
        print("backup:", bak)

def json_load(p):
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def json_save(p, data):
    bak = backup_file(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
    if bak:
        print("backup:", bak)

def json_walk(data, path, create=False):
    cur = data
    parts = path.split(".") if path else []
    for i, part in enumerate(parts[:-1]):
        is_idx = part.isdigit()
        if is_idx:
            idx = int(part)
            while len(cur) <= idx:
                cur.append({})
            cur = cur[idx]
            continue
        if part not in cur:
            if create:
                cur[part] = {}
            else:
                return None, None
        cur = cur[part]
    return cur, (parts[-1] if parts else None)

def json_get(p, path):
    data = json_load(p)
    cur, last = json_walk(data, path)
    if cur is None:
        sys.exit(2)
    if last is None:
        print(json.dumps(data, ensure_ascii=True))
        return
    if last.isdigit():
        idx = int(last)
        if not isinstance(cur, list) or idx >= len(cur):
            sys.exit(2)
        print(json.dumps(cur[idx], ensure_ascii=True))
    else:
        if last not in cur:
            sys.exit(2)
        print(json.dumps(cur[last], ensure_ascii=True))

def json_set(p, path, v):
    data = json_load(p)
    cur, last = json_walk(data, path, create=True)
    if last is None:
        raise ValueError("json path required")
    try:
        val = json.loads(v)
    except Exception:
        val = v
    if last.isdigit():
        idx = int(last)
        if not isinstance(cur, list):
            cur_list = []
            if isinstance(cur, dict):
                raise ValueError("json path points to list but parent is dict")
            cur = cur_list
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = val
    else:
        cur[last] = val
    json_save(p, data)

def json_unset(p, path):
    data = json_load(p)
    cur, last = json_walk(data, path)
    if cur is None or last is None:
        return
    if last.isdigit():
        idx = int(last)
        if isinstance(cur, list) and idx < len(cur):
            cur.pop(idx)
    else:
        if isinstance(cur, dict) and last in cur:
            del cur[last]
    json_save(p, data)

if action == "show-files":
    files = [
        "/etc/rpi-cam/config.env",
        "/etc/rpi-cam/recorder.conf",
        "/etc/rpi-cam/onvif.conf",
        "/etc/rpi-cam/meeting.json",
        "/etc/rpi-cam/wifi_failover.json",
        "/etc/rpi-cam/ap_mode.json",
        "/etc/rpi-cam/camera_profiles.json",
        "/etc/rpi-cam/csi_tuning.json",
        "/etc/rpi-cam/locked_recordings.json",
        "/etc/rpi-cam/debug_state.json",
    ]
    for f in files:
        exists = os.path.exists(f)
        print(f"{f} {'(ok)' if exists else '(missing)'}")
    sys.exit(0)

if is_json_file(path) or json_path:
    if action == "list":
        data = json_load(path)
        print(json.dumps(data, indent=2, ensure_ascii=True))
    elif action == "get":
        json_get(path, json_path)
    elif action == "set":
        json_set(path, json_path, value)
    elif action == "unset":
        json_unset(path, json_path)
    else:
        raise ValueError("Unsupported action for json: %s" % action)
else:
    if action == "list":
        env_list(path)
    elif action == "get":
        env_get(path, key)
    elif action == "set":
        env_set(path, key, value)
    elif action == "unset":
        env_unset(path, key)
    else:
        raise ValueError("Unsupported action for env: %s" % action)
"@

function Invoke-ConfigPython {
    param([string]$DeviceIP)
    $env = @(
        "ACTION=$(Escape-BashSingleQuotes $Action)",
        "CFG_FILE=$(Escape-BashSingleQuotes $File)",
        "KEY=$(Escape-BashSingleQuotes $Key)",
        "VALUE=$(Escape-BashSingleQuotes $Value)",
        "JSON_PATH=$(Escape-BashSingleQuotes $JsonPath)"
    ) -join " "

    $cmd = @"
$env python3 - <<'PY'
$pythonScript
PY
"@
    Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 20
}

switch ($Action) {
    "export" {
        Invoke-DeviceScp -DeviceIP $DeviceIP -Source $File -Destination $OutputFile
        Write-Host "Exported to: $OutputFile" -ForegroundColor Green
    }
    "import" {
        $remoteTmp = "/tmp/rtsp-config-import-$(Get-Random).tmp"
        Invoke-DeviceScp -DeviceIP $DeviceIP -Source $InputFile -Destination $remoteTmp -ToRemote
        Invoke-DeviceSsh -DeviceIP $DeviceIP -Command "sudo cp $remoteTmp $File && sudo rm -f $remoteTmp" -Timeout 10
        Write-Host "Imported into: $File" -ForegroundColor Green
    }
    default {
        Invoke-ConfigPython -DeviceIP $DeviceIP
    }
}

if ($RestartServices -and $Services.Count -gt 0) {
    $svcList = $Services -join " "
    Write-Host "Restarting services: $svcList" -ForegroundColor Yellow
    Invoke-DeviceSsh -DeviceIP $DeviceIP -Command "sudo systemctl restart $svcList" -Timeout 15
}

Write-Host "Done." -ForegroundColor Green
