// Smoke test: embed the wasm CPython (with pthreads) the way Ballistica does.
// Build + run with web/tests/run_embed_python.sh.
#include <Python.h>
#include <stdio.h>

int main(int argc, char** argv) {
  if (argc < 2) {
    printf("usage: embed_python <cpython-Lib-dir>\n");
    return 1;
  }
  PyConfig c;
  PyConfig_InitIsolatedConfig(&c);
  c.module_search_paths_set = 1;
  wchar_t* lib = Py_DecodeLocale(argv[1], NULL);
  PyWideStringList_Append(&c.module_search_paths, lib);
  PyStatus s = Py_InitializeFromConfig(&c);
  if (PyStatus_Exception(s)) {
    printf("init failed: %s\n", s.err_msg);
    return 1;
  }
  PyRun_SimpleString(
      "import sys, threading, json, zlib\n"
      "print('python', sys.version.split()[0], sys.platform)\n"
      "t = threading.Thread(target=lambda: print('worker thread ok'))\n"
      "t.start(); t.join()\n"
      "print('json+zlib ok', json.dumps({'a': len(zlib.compress(b'x'*1000))}))\n");
  Py_Finalize();
  return 0;
}
