#!/usr/bin/bash

set -euo pipefail

THIS_SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'  # No Color

function check_svc_status() {
  SVCS="$@"
  for SVC in $SVCS; do
    RUNNING=$( systemctl show "$SVC" -pActiveState,SubState --value | paste -sd ' ' - )
    TS=$( systemctl show "$SVC" -pActiveEnterTimestamp --value | paste -sd ' ' - )
    MPID=$( systemctl show "$SVC" -pMainPID --value | paste -sd ' ' - )

    if [[ "$RUNNING" == *running* ]]; then
      COLOR="$GREEN"
    elif [[ "$RUNNING" == *dead* ]]; then
      COLOR="$RED"
    else
      COLOR="$NC"
    fi

    printf "$COLOR$SVC\t$RUNNING$NC\tpid=$MPID\t$TS\n"
  done | column -t
}

services=()
for dir in "$THIS_SCRIPT_DIR"/*/; do
    name="$(basename $dir)"
    if [ -f "${dir}${name}.service" ]; then
        services+=("$name")
    fi
done

check_svc_status "${services[@]}"

