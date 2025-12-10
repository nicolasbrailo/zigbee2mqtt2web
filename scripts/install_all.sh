#!/usr/bin/bash

set -euo pipefail

SRC_ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../baticasa_doorbell
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../baticasa_buttons
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../mqtt_contact_mon
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../mqtt_doorbell_cam
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../mqtt_sensor_mon
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../mqtt_speaker_announce
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../mqtt_telegram
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../mqtt_whatsapp
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../cronenbergs
"$SRC_ROOT"/install_svc.sh "$SRC_ROOT"/../service_mon

