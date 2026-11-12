#!/usr/bin/env bash
# Download a non-desktop texture profile's asset packages for the web
# build, using the native (plus-enabled) client.
#
# The native client forced to another profile (BA_FORCE_TEXTURE_PROFILE)
# resolves and downloads that profile's flavors into a separate cache,
# leaving ~/.ballisticakit untouched. Its window renders black (the
# laptop GPU can't sample ASTC); it's closed as soon as every package
# has the profile.
#
# usage: web/fetch_flavors.sh [profile ...]  (default: mobile_v1 fallback_v1)
set -euo pipefail
cd "$(dirname "$0")/.."
BIN=build/cmake/debug/staged/ballisticakit
OUT=build/web/flavor-caches
NPKG=$(python3 -c "import json,os;print(len(json.load(open(os.path.expanduser(
  '~/.ballisticakit/cache/manifest.json')))['p']))")
for p in "${@:-mobile_v1 fallback_v1}"; do
  for prof in $p; do
    work=$OUT/.work-$prof
    rm -rf "$work" && mkdir -p "$work/cfg"
    cp ~/.ballisticakit/config.json "$work/cfg/"
    # Seed with the desktop cache so shared blobs aren't re-downloaded.
    rsync -a ~/.ballisticakit/cache/ "$work/cache/"
    (cd "$(dirname "$BIN")" && BA_FORCE_TEXTURE_PROFILE=$prof \
      exec ./ballisticakit -C "$OLDPWD/$work/cfg" -a "$OLDPWD/$work/cache") \
      >"$work/run.log" 2>&1 &
    pid=$!
    for _ in $(seq 300); do
      n=$(grep -o "textures/$prof\." "$work/cache/manifest.json" | wc -l)
      [ "$n" -ge "$NPKG" ] && break
      sleep 1
    done
    sleep 3
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    rm -rf "${OUT:?}/$prof" && mv "$work/cache" "$OUT/$prof" && rm -rf "$work"
    echo "$prof: $(du -sh "$OUT/$prof" | cut -f1)"
  done
done
