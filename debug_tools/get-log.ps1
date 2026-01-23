# get-log.ps1 - Alias compat pour get_logs.ps1
# Version: 1.0.0
#
# Usage:
#   .\get-log.ps1 -Auto -DeviceKey "ABC123" -Tool logs
#   .\get-log.ps1 -Tool collect -OutputDir "./logs"

& (Join-Path $PSScriptRoot "get_logs.ps1") @args
