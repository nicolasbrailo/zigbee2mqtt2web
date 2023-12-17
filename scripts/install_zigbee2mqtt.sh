#!/usr/bin/bash
set -euo pipefail

# See https://www.zigbee2mqtt.io/guide/installation/01_linux.html#installing

Z2M_INSTALL_PATH="$1"
Z2M2W_RUN_PATH="$2"
Z2M_RUN_PATH="$Z2M2W_RUN_PATH/zigbee2mqtt"
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "systemctl status zigbee2mqtt.service" > "$Z2M2W_RUN_PATH/zigbee2mqtt_active.sh"
echo "sudo journalctl --follow --unit zigbee2mqtt" > "$Z2M2W_RUN_PATH/zigbee2mqtt_logs.sh"
echo "sudo systemctl restart zigbee2mqtt.service" > "$Z2M2W_RUN_PATH/zigbee2mqtt_restart.sh"
chmod +x "$Z2M2W_RUN_PATH/zigbee2mqtt_active.sh"
chmod +x "$Z2M2W_RUN_PATH/zigbee2mqtt_logs.sh"
chmod +x "$Z2M2W_RUN_PATH/zigbee2mqtt_restart.sh"

systemctl is-active --quiet zigbee2mqtt.service && echo "Zigbee2Mqtt is running!" && exit 0

if [[ -d "$Z2M_INSTALL_PATH" ]]; then
  echo "Not installing Zigbee2Mqtt: already exists at $Z2M_INSTALL_PATH. Remove it if you want to reinstall"
  exit 0
fi

sudo apt-get install --assume-yes nodejs git make g++ gcc > /dev/null

# With set -e, this will terminate the script if node or npm are not present
node --version > /dev/null
npm --version > /dev/null

mkdir "$Z2M_INSTALL_PATH"
mkdir -p "$Z2M_RUN_PATH"
pushd "$Z2M_INSTALL_PATH"

git clone --depth 1 https://github.com/Koenkk/zigbee2mqtt.git .
npm ci
npm run build

popd


ZIGBEE_ADAPTER_PATH=/dev/ttyUSB0
if [ ! -e "$ZIGBEE_ADAPTER_PATH" ]; then
  echo "Can't find Zigbee adapter at $ZIGBEE_ADAPTER_PATH, trying alternate path"
  ZIGBEE_ADAPTER_PATH=/dev/ttyACM0
fi
if [ ! -e "$ZIGBEE_ADAPTER_PATH" ]; then
  echo "Can't find Zigbee adapter at $ZIGBEE_ADAPTER_PATH and out of guesses"
  exit 1
fi

echo "Assuming Zigbee adapter lives at $ZIGBEE_ADAPTER_PATH"
echo "If this is wrong, correct it in $Z2M_RUN_PATH/configuration.yaml"

if ! test -w "$ZIGBEE_ADAPTER_PATH"; then
  ADAPTER_GROUP=$( ls -lha /dev/ttyACM0 | awk '{print $4}' )
  echo -e "\033[0;31m"
  echo "Can't write to $ZIGBEE_ADAPTER_PATH, will try to fix permissions by adding $(whoami) to group $ADAPTER_GROUP"
  echo "This may or may not fix the permissions, but there is no way to know without logging out and in to refresh groups"
  echo -e "\033[0m"
  sudo usermod  -a -G "$ADAPTER_GROUP" "$(whoami)"
fi

# Configure, install as service
cat "$SCRIPT_DIR/zigbee2mqtt.conf.template" | \
  sed "s|#ZIGBEE_ADAPTER_PATH#|$ZIGBEE_ADAPTER_PATH|g" | \
  sed "s|#Z2M_RUN_PATH#|$Z2M_RUN_PATH|g" | \
  sed "s|#Z2M_INSTALL_PATH#|$Z2M_INSTALL_PATH|g" | \
  sed "s|#RUN_USER#|$(whoami)|g" | \
  sudo tee >/dev/null "$Z2M_RUN_PATH/configuration.yaml"

cat "$SCRIPT_DIR/zigbee2mqtt.service.template" | \
  sed "s|#ZIGBEE_ADAPTER_PATH#|$ZIGBEE_ADAPTER_PATH|g" | \
  sed "s|#Z2M_RUN_PATH#|$Z2M_RUN_PATH|g" | \
  sed "s|#Z2M_INSTALL_PATH#|$Z2M_INSTALL_PATH|g" | \
  sed "s|#RUN_USER#|$(whoami)|g" | \
  sudo tee >/dev/null ./zigbee2mqtt.service

sudo mv ./zigbee2mqtt.service /etc/systemd/system/zigbee2mqtt.service

sudo systemctl stop zigbee2mqtt.service | true > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable zigbee2mqtt.service
sudo systemctl start zigbee2mqtt.service

if ! systemctl is-active --quiet zigbee2mqtt.service ; then
  echo -e "\033[0;31m"
  echo "Failed to install zigbee2mqtt"
  echo -e "\033[0m"
  sudo journalctl --unit zigbee2mqtt.service
  exit 1
fi
