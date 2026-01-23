#!/usr/bin/env bash
#===============================================================================
# File: rpi_av_rtsp_recorder_wrapper.sh
# Location: /usr/local/bin/rpi_av_rtsp_recorder_wrapper.sh
#
# Purpose: Wrapper script that loads configuration from web manager before
#          starting the RTSP recorder. Use this instead of calling the main
#          script directly when using the web management interface.
#===============================================================================

set -euo pipefail

CONFIG_FILE="/etc/rpi-cam/config.env"

# Load configuration if available
if [[ -f "$CONFIG_FILE" ]]; then
    echo "[$(date "+%Y-%m-%d %H:%M:%S")] Loading configuration from $CONFIG_FILE"
    set -a  # Export all variables
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
    set +a
else
    echo "[$(date "+%Y-%m-%d %H:%M:%S")] No config file found at $CONFIG_FILE, using defaults"
fi

# Execute the main RTSP recorder script
exec /usr/local/bin/rpi_av_rtsp_recorder.sh "$@"
