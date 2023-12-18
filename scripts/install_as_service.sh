#!/usr/bin/bash
set -euo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SRC_ROOT=$(dirname "$SCRIPT_DIR")
Z2M2W_INSTALL_NAME=${1-zigbee2mqtt2web_run}
Z2M_INSTALL_PATH="/home/$USER/zigbee2mqtt"
Z2M2W_RUN_PATH="/home/$USER/$Z2M2W_INSTALL_NAME"

"$SCRIPT_DIR/install_dep_svcs.sh"

if [ ! -f "$SRC_ROOT/Pipfile" ]; then
  if [[ $(arch) -eq "x86_64" ]]; then
    echo "Automatically selecting x86 Pipfile"
    cp "$SRC_ROOT/Pipfile.x86" "$SRC_ROOT/Pipfile"
  else
    echo -e "\033[0;31m"
    echo "Can't find Pipfile, make sure you select between Pipfile.x86 or Pipfile.arm"
    echo -e "\033[0m"
    exit 1
  fi
fi

echo "systemctl status zigbee2mqtt2web.service" > "$Z2M2W_RUN_PATH/zigbee2mqtt2web_active.sh"
echo "sudo journalctl --follow --unit zigbee2mqtt2web" > "$Z2M2W_RUN_PATH/zigbee2mqtt2web_logs.sh"
echo "sudo systemctl restart zigbee2mqtt2web.service" > "$Z2M2W_RUN_PATH/zigbee2mqtt2web_restart.sh"
chmod +x "$Z2M2W_RUN_PATH/zigbee2mqtt2web_active.sh"
chmod +x "$Z2M2W_RUN_PATH/zigbee2mqtt2web_logs.sh"
chmod +x "$Z2M2W_RUN_PATH/zigbee2mqtt2web_restart.sh"

echo "sudo journalctl --follow --unit zigbee2mqtt2web --unit zigbee2mqtt --unit mosquitto" > "$Z2M2W_RUN_PATH/tail_logs.sh"
chmod +x "$Z2M2W_RUN_PATH/tail_logs.sh"

# authbind -> run in port 80 with no root
sudo touch /etc/authbind/byport/80
sudo chmod 777 /etc/authbind/byport/80
sudo touch /etc/authbind/byport/443
sudo chmod 777 /etc/authbind/byport/443

cat "$SCRIPT_DIR/zigbee2mqtt2web.service.template" | \
	sed "s|#SRC_ROOT#|$SRC_ROOT|g" | \
  sed "s|#Z2M2W_RUN_PATH#|$Z2M2W_RUN_PATH|g" | \
  sed "s|#RUN_USER#|$(whoami)|g" | \
	sudo tee >/dev/null /etc/systemd/system/zigbee2mqtt2web.service

cp "$SRC_ROOT/zigbee2mqtt2web.config.json" "$Z2M2W_RUN_PATH/zigbee2mqtt2web.config.json"

pushd "$Z2M2W_RUN_PATH"
PIPENV_PIPFILE="$SRC_ROOT/Pipfile" python3 -m pipenv --python $(which python3) install
popd

sudo systemctl stop zigbee2mqtt2web | true
sudo systemctl daemon-reload
sudo systemctl enable zigbee2mqtt2web
sudo systemctl start zigbee2mqtt2web
sudo systemctl status zigbee2mqtt2web
