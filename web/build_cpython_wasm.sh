#!/usr/bin/env bash
# Builds CPython 3.14 for wasm32-emscripten WITH pthreads, as a static lib
# (libpython3.14.a) that Ballistica can embed.
# Expects ~/projects/bombsquade-port/{emsdk,cpython} (cpython on branch
# bombsquad-wasm, emsdk activated at 4.0.12 = version pinned by CPython).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/cpython"
source "$ROOT/emsdk/emsdk_env.sh" >/dev/null 2>&1
P="python3 Platforms/emscripten"
# Native helper python: must NOT get the wasm flags (so no 'build all').
$P configure-build-python
$P make-build-python
# Everything wasm gets -pthread so it links into a shared-memory binary.
export EMCC_CFLAGS=-pthread
$P make-dependencies
# --host-runner: the script otherwise tries to install node via nvm.
$P configure-host --host-runner "$(command -v node)" -- \
  --enable-wasm-pthreads --disable-wasm-dynamic-linking
# make-host ends by running python.sh --version, which fails for pthread
# builds (node_entry.mjs isn't pthread-aware). libpython3.14.a is fine.
$P make-host || true
ls -la cross-build/wasm32-emscripten/build/python/libpython3.14.a
