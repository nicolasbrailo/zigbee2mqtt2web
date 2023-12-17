SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SRC_ROOT="$(dirname "$SCRIPT_DIR")"

Z2M2W_RUN_PATH="$1"

# authbind -> run in port 80 with no root
sudo touch /etc/authbind/byport/80
sudo chmod 777 /etc/authbind/byport/80
sudo touch /etc/authbind/byport/443
sudo chmod 777 /etc/authbind/byport/443

cat "$SCRIPT_DIR/zigbee2mqtt2web.service.template" | \
	sed "s|#SRC_ROOT#|$SRC_ROOT|g" | \
  sed "s|#Z2M2W_RUN_PATH#|$Z2M2W_RUN_PATH|g" | \
	sudo tee >/dev/null /etc/systemd/system/zigbee2mqtt2web.service

cp "$SRC_ROOT/config.template.json" "$Z2M2W_RUN_PATH/config.json"

sudo systemctl stop zigbee2mqtt2web | true
sudo systemctl daemon-reload
sudo systemctl disable zigbee2mqtt2web
#sudo systemctl enable zigbee2mqtt2web
#sudo systemctl start zigbee2mqtt2web
#sudo systemctl status zigbee2mqtt2web
