#!/usr/bin/env bash
# Write .br and .gz siblings for the big files in build/web/dist, which
# web/serve.py sends with Content-Encoding to clients that accept it.
# Each is written to a temp name and renamed, so a client never gets a
# half-written file while the server is live (serve.py also skips a
# sibling older than its source). brotli -q 9 is ~10x faster than -q 11
# for a few percent less compression on this data.
set -euo pipefail
cd "$(dirname "$0")/../build/web/dist"
for f in ./*.data ./*.wasm ./*.js; do
  (brotli -q 9 -f -o "$f.br.tmp" "$f" && mv -f "$f.br.tmp" "$f.br") &
  (pigz -9 -c "$f" > "$f.gz.tmp" && mv -f "$f.gz.tmp" "$f.gz") &
done
wait
ls -la
