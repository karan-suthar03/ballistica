#!/usr/bin/env bash
# Links web/tests/embed_python.c against the wasm CPython and runs it in node.
# NOTE: NODERAWFS can't list directories through symlinks, so pass a real path.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # ~/projects/bombsquade-port
C="$ROOT/cpython"
B="$C/cross-build/wasm32-emscripten/build/python"
OUT="${OUT:-$(mktemp -d)}"
source "$ROOT/emsdk/emsdk_env.sh" >/dev/null 2>&1
HACL=$(find "$B/Modules/_hacl" -name '*.o')
emcc -O1 -pthread -sPROXY_TO_PTHREAD -sNODERAWFS -sALLOW_MEMORY_GROWTH \
  -sSTACK_SIZE=5MB -sWASM_BIGINT -sEXIT_RUNTIME \
  -sEXPORTED_FUNCTIONS=_main,__PyRuntime,__PyEM_EMSCRIPTEN_TRAMPOLINE_OFFSET \
  -I"$C/Include" -I"$B" "$(dirname "$0")/embed_python.c" \
  "$B/libpython3.14.a" $HACL "$B/Modules/expat/libexpat.a" \
  -L"$C/cross-build/wasm32-emscripten/prefix/lib" -lmpdec -lffi \
  -sUSE_ZLIB -sUSE_BZIP2 -o "$OUT/embed.js"
node "$OUT/embed.js" "$C/Lib"
