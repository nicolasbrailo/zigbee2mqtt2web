#!/usr/bin/bash
set -euo pipefail

RUN_PATH="$1"
LOG_DIR="$1/logs"

systemctl is-active --quiet mosquitto.service && echo "Mosquitto is running!" && exit 0

sudo apt-get install --assume-yes mosquitto mosquitto-clients
sudo systemctl enable mosquitto.service

if ! systemctl is-active --quiet mosquitto.service ; then
  echo -e "\033[0;31m"
  echo "Failed to install mosquitto"
  echo -e "\033[0m"
  sudo journalctl -u mosquitto
  exit 1
fi

# Config mosquitto logs
cat /etc/mosquitto/mosquitto.conf | grep -v log_dest > mosquitto.new.conf
echo "log_dest file $LOG_DIR/mosquitto.log" >> mosquitto.new.conf
sudo mv mosquitto.new.conf /etc/mosquitto/mosquitto.conf

echo "systemctl status mosquitto.service" > "$RUN_PATH/mosquitto_active.sh"
echo "sudo journalctl --follow --unit mosquitto" > "$RUN_PATH/mosquitto_logs.sh"
echo "sudo systemctl restart mosquitto.service" > "$RUN_PATH/mosquitto_restart.sh"
chmod +x "$RUN_PATH/mosquitto_active.sh"
chmod +x "$RUN_PATH/mosquitto_logs.sh"
chmod +x "$RUN_PATH/mosquitto_restart.sh"

# Apply new config
. "$RUN_PATH/mosquitto_restart.sh"

