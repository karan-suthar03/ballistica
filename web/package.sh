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
# Overlay the Python sources from src so web-only edits/modules
# (baenv.py, bawebshims.py, ...) apply without a full native asset build.
rsync -a --exclude __pycache__ src/assets/ba_data/python/ "$ROOT/ba_data/python/"
# Shared packages that live under tools/ and get copied into ba_data.
for pkg in bacommon efro; do
  rsync -a --exclude __pycache__ "tools/$pkg/" "$ROOT/ba_data/python/$pkg/"
done

# Python stdlib, minus things a game never needs.
rsync -a --exclude __pycache__ \
  --exclude test/ --exclude tests/ --exclude idlelib/ --exclude tkinter/ \
  --exclude turtledemo/ --exclude ensurepip/ --exclude venv/ \
  --exclude pydoc_data/ --exclude lib2to3/ --exclude turtle.py \
  --exclude _pyrepl/ --exclude __phello__/ \
  "$CPY/Lib/" "$ROOT/pylib/"
cp "$SYSCFG"/_sysconfigdata_*.py "$SYSCFG"/_sysconfig_vars_*.json "$ROOT/pylib/"

# Full asset packages. Web builds have no plus, so they can't resolve or
# download packages from the cloud themselves; instead we ship the ones a
# native (plus-enabled) build already downloaded. With every desired
# flavor present locally, the asset subsystem takes its offline fast path.
# Lands at ~/.ballisticakit/cache in the virtual FS (HOME=/home/web_user).
# One cache per texture profile: desktop from the native build's own
# cache, the others from web/fetch_flavors.sh. split_assets.py merges
# their manifests and splits each profile's textures into its own
# package, so a browser only downloads the set its GPU can use.
NATIVE_CACHE="${NATIVE_CACHE:-$HOME/.ballisticakit/cache}"
FLAVORS=$WEB/flavor-caches
SPLIT=$WEB/assets-split
CACHE_VFS=/home/web_user/.ballisticakit/cache
PROFILES="desktop_v1 mobile_v1 fallback_v1"
args=("desktop_v1=$NATIVE_CACHE")
for p in mobile_v1 fallback_v1; do
  [ -f "$FLAVORS/$p/manifest.json" ] || {
    echo "missing $FLAVORS/$p; run web/fetch_flavors.sh $p" >&2; exit 1; }
  args+=("$p=$FLAVORS/$p")
done
python3 web/split_assets.py "$SPLIT" "${args[@]}"
mkdir -p "$ROOT$CACHE_VFS"
rsync -a "$SPLIT/base/" "$ROOT$CACHE_VFS/"

echo "virtual FS contents:"; du -sh "$ROOT"/*

python3 "$EMSDK/upstream/emscripten/tools/file_packager.py" \
  "$DIST/ballisticakit.data" --preload "$ROOT@/" \
  --js-output="$DIST/ballisticakit.data.js" --no-node >/dev/null
for p in $PROFILES; do
  python3 "$EMSDK/upstream/emscripten/tools/file_packager.py" \
    "$DIST/tex-$p.data" --preload "$SPLIT/tex-$p@$CACHE_VFS" \
    --js-output="$DIST/tex-$p.data.js" --no-node >/dev/null
done

# file_packager's progress divides decompressed bytes read by the
# Content-Length, which is the compressed size when serve.py sends .br/.gz.
# Use the package's real size instead.
sed -i "s/Number(headers.get('Content-Length') ?? packageSize)/packageSize/" \
  "$DIST"/*.data.js
cp "$WEB/ballisticakit.js" "$WEB/ballisticakit.wasm" "$DIST/"
cp web/shell/*.html web/shell/*.js web/shell/*.css web/shell/*.png \
  web/shell/*.webmanifest "$DIST/"
sed -i "s/__BUILD__/$(date +%s)/g" "$DIST/index.html"
# Version shown on the loading screen: commit + build time (IST).
VERSION="$(git rev-parse --short HEAD)$(git diff --quiet HEAD -- web src || echo +)  ·  $(TZ=Asia/Kolkata date '+%d %b %H:%M')"
sed -i "s/__VERSION__/$VERSION/g" "$DIST/index.html"
web/compress.sh >/dev/null
ls -la "$DIST"
