#!/usr/bin/bash

set -euo pipefail

# Helper to compile a single babel js input to a single output (ie will break with globbing)

RUNDIR=$(readlink -f .)
SRC_ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
BABEL_ROOT="$SRC_ROOT/build/npm"

if [ ! -f "$BABEL_ROOT/babel.config.json" ]; then
  cp ./babel.config.json "$BABEL_ROOT/babel.config.json"
fi

# Run from root of node install dir, otherwise deps aren't found
pushd "$BABEL_ROOT"
./node_modules/.bin/babel --config-file ./babel.config.json \
    --no-comments --compact true --minified \
    "$RUNDIR/$1" -o "$RUNDIR/$2"
popd

