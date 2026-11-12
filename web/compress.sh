#!/usr/bin/env bash
# Write .br and .gz siblings for the big files in build/web/dist, which
# web/serve.py sends with Content-Encoding to clients that accept it.
# Runs all files in parallel; brotli -q 9 is ~10x faster than -q 11 for
# a few percent less compression on this data.
set -euo pipefail
cd "$(dirname "$0")/../build/web/dist"
rm -f ./*.br ./*.gz
for f in ./*.data ./*.wasm ./*.js; do
  brotli -q 9 -f -o "$f.br" "$f" &
  pigz -9 -k -f "$f" &
done
wait
ls -la
