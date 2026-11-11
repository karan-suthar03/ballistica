# Released under the MIT License. See LICENSE for details.
#
"""Compatibility shims for running under emscripten (web builds).

Imported by baenv before anything else on sys.platform == 'emscripten'.
"""

from __future__ import annotations

import os
import socket

_installed = False


class _PipeEnd:
    """One end of an os.pipe() posing as a socket.

    asyncio's selector event loop wakes itself up through a
    socket.socketpair() 'self-pipe'. Emscripten's socket emulation can't
    listen()/accept() so the stdlib socketpair fallback fails; a plain
    pipe (which emscripten can poll) does the same job.
    """

    def __init__(self, fd: int) -> None:
        self._fd = fd

    def fileno(self) -> int:
        return self._fd

    def setblocking(self, flag: bool) -> None:
        os.set_blocking(self._fd, flag)

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        del flags
        try:
            return os.read(self._fd, bufsize)
        except BlockingIOError:
            raise
        except OSError as exc:
            # Emscripten's pipefs reports an empty pipe as EAGAIN-ish.
            raise BlockingIOError(str(exc)) from exc

    def recv_into(self, buffer: bytearray, nbytes: int = 0) -> int:
        data = self.recv(nbytes or len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def send(self, data: bytes, flags: int = 0) -> int:
        del flags
        return os.write(self._fd, data)

    def sendall(self, data: bytes, flags: int = 0) -> None:
        del flags
        view = memoryview(data)
        while view:
            view = view[os.write(self._fd, view) :]

    def close(self) -> None:
        if self._fd != -1:
            try:
                os.close(self._fd)
            finally:
                self._fd = -1

    def __enter__(self) -> _PipeEnd:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _pipe_socketpair(*args: object, **kwargs: object) -> tuple:
    del args, kwargs
    rfd, wfd = os.pipe()
    # asyncio reads from the first and writes to the second.
    return _PipeEnd(rfd), _PipeEnd(wfd)


def install() -> None:
    """Install all web shims (idempotent)."""
    global _installed  # pylint: disable=global-statement
    if _installed:
        return
    _installed = True
    socket.socketpair = _pipe_socketpair  # type: ignore[assignment]
    _stub_urllib3_pyodide()


def _stub_urllib3_pyodide() -> None:
    """Keep urllib3 from loading its Pyodide (fetch API) integration.

    On sys.platform == 'emscripten' urllib3 imports
    urllib3.contrib.emscripten, which needs Pyodide's 'js' module. We're
    plain emscripten CPython, not Pyodide, so register a no-op stand-in.
    """
    import sys
    import types

    name = 'urllib3.contrib.emscripten'
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.inject_into_urllib3 = lambda: None  # type: ignore[attr-defined]
        sys.modules[name] = mod
