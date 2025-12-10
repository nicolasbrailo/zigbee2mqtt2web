#!/usr/bin/bash

set -euo pipefail

if [ -z "${1+x}" ]; then
  echo "Missing arg: target service path"
  exit 1
fi

TGT_SVC_SRC=$( readlink -f "$1" )
TGT_SVC_NAME=$( basename "$TGT_SVC_SRC" )
SVC_RUN_BASE="/home/$USER/run/baticasa"
TGT_SVC_RUN="$SVC_RUN_BASE/$TGT_SVC_NAME"

# Check if service exists
if [ ! -d "$TGT_SVC_RUN" ]; then
  echo "Error: Service $TGT_SVC_NAME is not installed (no directory at $TGT_SVC_RUN)"
  exit 1
fi

echo "Uninstalling service $TGT_SVC_NAME"

# Stop the service
if [ -f "$TGT_SVC_RUN/stop.sh" ]; then
  echo "Stopping service..."
  "$TGT_SVC_RUN/stop.sh"
fi

# Disable the service
sudo systemctl disable "$TGT_SVC_NAME"

# Remove the systemd service file
if [ -f "/etc/systemd/system/$TGT_SVC_NAME.service" ]; then
  echo "Removing systemd service file..."
  sudo rm "/etc/systemd/system/$TGT_SVC_NAME.service"
fi

# Remove installed files (but keep config.json)
echo "Removing installed files (keeping config.json)..."
rm -f "$TGT_SVC_RUN/Pipfile"
rm -f "$TGT_SVC_RUN/Pipfile.lock"
rm -f "$TGT_SVC_RUN/$TGT_SVC_NAME.service"
rm -f "$TGT_SVC_RUN/restart_and_logs.sh"
rm -f "$TGT_SVC_RUN/stop.sh"
rm -f "$TGT_SVC_RUN/start.sh"
rm -f "$TGT_SVC_RUN/logs.sh"
# Cleanup virtualenv
rm -rf "$TGT_SVC_RUN/.venv"

sudo systemctl daemon-reload

echo "Service $TGT_SVC_NAME uninstalled successfully"
