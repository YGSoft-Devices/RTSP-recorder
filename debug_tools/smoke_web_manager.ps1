param(
    [string]$IP = "192.168.1.124",
    [int]$Port = 5000,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$runRemote = Join-Path $PSScriptRoot "run_remote.ps1"

function Invoke-RemoteCommand {
    param([string]$Command)
    & $runRemote -IP $IP $Command
}

if (-not $NoStart) {
    Invoke-RemoteCommand "sudo systemctl start rpi-cam-webmanager" | Out-Null
}

$serviceStatus = Invoke-RemoteCommand "systemctl is-active rpi-cam-webmanager"
if ($serviceStatus -notmatch "active") {
    Write-Error "rpi-cam-webmanager is not active: $serviceStatus"
    exit 1
}

$pythonSmoke = @'
import json
import sys
import urllib.request

base = f"http://127.0.0.1:{sys.argv[1]}"
endpoints = {
    "/api/status": ["status"],
    "/api/config": ["config"],
    "/api/onvif/status": ["success"],
    "/api/system/health": ["status"],
    "/api/system/info": ["success"]
}

for path, keys in endpoints.items():
    url = base + path
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
        data = json.loads(payload)
    except Exception as exc:
        print(f"FAIL {path}: {exc}")
        sys.exit(2)

    missing = [key for key in keys if key not in data]
    if missing:
        print(f"FAIL {path}: missing keys {missing}")
        sys.exit(3)

    print(f"OK {path}")

print("SMOKE_OK")
'@

$remoteScript = @"
python3 - "$Port" <<'PY'
$pythonSmoke
PY
"@

Invoke-RemoteCommand $remoteScript -ErrorAction Stop | Write-Output
