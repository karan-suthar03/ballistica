#!/usr/bin/env bash
# Assembles a runnable web build in build/web/dist:
#   index.html, ballisticakit.{js,wasm}, ballisticakit.data(.js)
# The .data file is emscripten's preloaded virtual FS containing
#   /ba_data  (game scripts + assets, from the native staged build)
#   /pylib    (trimmed CPython stdlib + emscripten sysconfigdata)
# Prereqs: native `make cmake-build` (for staged ba_data) and the
# emscripten engine build in build/web.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJ="$(cd .. && pwd)"
STAGED=build/cmake/debug/staged
WEB=build/web
ROOT=$WEB/root
DIST=$WEB/dist
CPY="$PROJ/cpython"
SYSCFG="$CPY/cross-build/wasm32-emscripten/build/python/build/lib.emscripten-4.0.12-wasm32-3.14"

source "$PROJ/emsdk/emsdk_env.sh" >/dev/null 2>&1

rm -rf "$ROOT" && mkdir -p "$ROOT" "$DIST"

# Game data (deref symlinks: the virtual FS can't follow host links).
rsync -aL --exclude __pycache__ "$STAGED/ba_data/" "$ROOT/ba_data/"

# Python stdlib, minus things a game never needs.
rsync -a --exclude __pycache__ \
  --exclude test/ --exclude tests/ --exclude idlelib/ --exclude tkinter/ \
  --exclude turtledemo/ --exclude ensurepip/ --exclude venv/ \
  --exclude pydoc_data/ --exclude lib2to3/ --exclude turtle.py \
  --exclude _pyrepl/ --exclude __phello__/ \
  "$CPY/Lib/" "$ROOT/pylib/"
cp "$SYSCFG"/_sysconfigdata_*.py "$SYSCFG"/_sysconfig_vars_*.json "$ROOT/pylib/"

echo "virtual FS contents:"; du -sh "$ROOT"/*

python3 "$EMSDK/upstream/emscripten/tools/file_packager.py" \
  "$DIST/ballisticakit.data" --preload "$ROOT@/" \
  --js-output="$DIST/ballisticakit.data.js" --no-node >/dev/null

cp "$WEB/ballisticakit.js" "$WEB/ballisticakit.wasm" "$DIST/"
cp web/shell/index.html "$DIST/"
ls -la "$DIST"
