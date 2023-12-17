#!/usr/bin/bash
set -euo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
Z2M2W_INSTALL_NAME=${1-zigbee2mqtt2web_run}
Z2M_INSTALL_PATH="/home/$USER/zigbee2mqtt"
Z2M2W_RUN_PATH="/home/$USER/$Z2M2W_INSTALL_NAME"

"$SCRIPT_DIR/install_dep_svcs.sh"
"$SCRIPT_DIR/install_zigbee2mqtt2web.sh" "$Z2M2W_RUN_PATH"

echo "All system services should be installed now"
