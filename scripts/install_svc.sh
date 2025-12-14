#!/usr/bin/bash

set -euo pipefail

if [ -z "${1+x}" ]; then
  echo "Missing arg: target service path"
  exit 1
fi

SRC_ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
TGT_SVC_SRC=$( readlink -f "$1" )
TGT_SVC_NAME=$( basename "$TGT_SVC_SRC" )
SVC_RUN_BASE="/home/$USER/run/baticasa"
TGT_SVC_RUN="$SVC_RUN_BASE/$TGT_SVC_NAME"

echo "Installing service $TGT_SVC_NAME from $TGT_SVC_SRC"

function ensure_file() {
  FN="$1"
  if [ ! -f "$TGT_SVC_SRC/$FN" ]; then
    echo "$TGT_SVC_SRC doesn't look like a service, no $FN found"
    exit 1
  fi
}

ensure_file "$TGT_SVC_NAME.py"
ensure_file Pipfile.lock
ensure_file Pipfile

if [ -f "$TGT_SVC_RUN/config.json" ]; then
  echo "$TGT_SVC_SRC already has a config.json file, will not create new one"
elif [ ! -f "$TGT_SVC_SRC/config.json" ]; then
  echo "$TGT_SVC_SRC doesn't have a config.json file, create one from the template"
  exit 1
fi

# Check if this service already exists
if [ -f "$TGT_SVC_RUN/stop.sh" ]; then
  echo "Service $TGT_SVC_NAME already exists, stopping old service first..."
  "$TGT_SVC_RUN/stop.sh"
fi

# Create target run dir and its virtual env
mkdir -p "$TGT_SVC_RUN"
pushd "$TGT_SVC_RUN"
cp "$TGT_SVC_SRC/Pipfile" .
cp "$TGT_SVC_SRC/Pipfile.lock" .

if [ ! -f "$TGT_SVC_RUN/config.json" ]; then
  mv "$TGT_SVC_SRC/config.json" config.json
fi

PIPENV_VENV_IN_PROJECT=1 pipenv sync
popd

read -r -d '' SVC_TMPL <<EOF || true
[Unit]
Description=$TGT_SVC_NAME
After=mosquitto.target
Wants=mosquitto.target

[Service]
ExecStartPre=/usr/bin/mkdir -m 740 -p "$TGT_SVC_RUN"
Environment=
ExecStart=pipenv run python3 "$TGT_SVC_SRC/$TGT_SVC_NAME.py"
WorkingDirectory=/home/$USER/run/baticasa/$TGT_SVC_NAME
Restart=always
RestartSec=10s
User=$USER

[Install]
WantedBy=multi-user.target
EOF

read -r -d '' RESTART_AND_LOGS_TMPL <<EOF || true
  SCRIPT_DIR="\$(cd -- "\$(dirname -- "\${BASH_SOURCE[0]}")" && pwd)"
  sudo systemctl restart '$TGT_SVC_NAME' && "\$SCRIPT_DIR/logs.sh"
EOF

echo "$SVC_TMPL" > "$TGT_SVC_RUN/$TGT_SVC_NAME.service"
echo "$RESTART_AND_LOGS_TMPL" > "$TGT_SVC_RUN/restart_and_logs.sh"
chmod +x "$TGT_SVC_RUN/restart_and_logs.sh"
echo "sudo systemctl stop '$TGT_SVC_NAME'" > "$TGT_SVC_RUN/stop.sh"
chmod +x "$TGT_SVC_RUN/stop.sh"
echo "sudo systemctl start '$TGT_SVC_NAME'" > "$TGT_SVC_RUN/start.sh"
chmod +x "$TGT_SVC_RUN/start.sh"
cp "$SRC_ROOT/journal_parse.jq" "$SVC_RUN_BASE/journal_parse.jq"
echo "journalctl --follow --output=json --unit '$TGT_SVC_NAME' | jq -r -f '$SVC_RUN_BASE/journal_parse.jq'" > "$TGT_SVC_RUN/logs.sh"
chmod +x "$TGT_SVC_RUN/logs.sh"

cp "$SRC_ROOT/services_status.sh" "$SVC_RUN_BASE/services_status.sh"
CMD_LOG_ALL="journalctl --follow --output=json"
ALL_UNITS=""
for SVC in $( ls -d $SVC_RUN_BASE/* ); do
  MAYBE_SVC_NAME=$(basename "$SVC")
  if [ -f "$SVC/$MAYBE_SVC_NAME.service" ]; then
    CMD_LOG_ALL+=" --unit '$MAYBE_SVC_NAME'"
    ALL_UNITS+=" '$MAYBE_SVC_NAME'"
  fi
done

echo "$CMD_LOG_ALL | jq -r -f '$SVC_RUN_BASE/journal_parse.jq'" > "$SVC_RUN_BASE/logs.sh"
chmod +x "$SVC_RUN_BASE/logs.sh"
echo "check_svc_status $ALL_UNITS" >> "$SVC_RUN_BASE/services_status.sh"
chmod +x "$SVC_RUN_BASE/services_status.sh"
echo "echo 'Will restart EVERYTHING at the same time. Sure? Ctrl-c to cancel.' && read && sudo systemctl restart $ALL_UNITS" > "$SVC_RUN_BASE/restart_all.sh"
chmod +x "$SVC_RUN_BASE/restart_all.sh"

# Install. Symlink may already exist if the service already did.
sudo ln -s "$TGT_SVC_RUN/$TGT_SVC_NAME.service" "/etc/systemd/system/$TGT_SVC_NAME.service" || true
sudo systemctl daemon-reload

sudo systemctl enable "$TGT_SVC_NAME"
sudo systemctl start "$TGT_SVC_NAME"

