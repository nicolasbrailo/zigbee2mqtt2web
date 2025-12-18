#!/usr/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME=$( basename "$SCRIPT_DIR" )

echo "This script will create an SSL cert for this $SERVICE_NAME service. Restart service to apply."
echo "If you change your mind, remove the generated key.pem and cert.pem to use http."
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 3650 -nodes -subj '/CN=ZMWservice'

if [ ! -f "$SCRIPT_DIR/Pipfile.lock" ]; then
  echo "$SERVICE_NAME doesn't look like a ZMW service. Certs generated, but they may do nothing."
  exit 1
fi

