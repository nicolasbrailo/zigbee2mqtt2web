#!/usr/bin/bash

set -euo pipefail

DEPS_DEST_PATH="www/extjsdeps"
DEPS_READ_FROM="www/devel.html"

rm -rf "$DEPS_DEST_PATH"
mkdir -p "$DEPS_DEST_PATH"

for jsdep in $(cat "$DEPS_READ_FROM" | grep 'src="https://' | awk -F'src=' '{print $2}' | tr -d '"'); do
  echo "Localize $jsdep"
  wget --directory-prefix="$DEPS_DEST_PATH" $jsdep
done

echo "Copypaste:"
for jsdep in "$DEPS_DEST_PATH"/*.js; do
  echo "<script src='$jsdep'></script>"
done

