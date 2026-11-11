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
    _stub_ssl()
    _stub_urllib3_pyodide()


def _stub_ssl() -> None:
    """Provide a minimal 'ssl' module (the wasm CPython has no _ssl).

    Browsers can't do raw TLS sockets anyway, and web builds have no
    plus/master-server, so we only need the names babase touches at
    import/setup time. Deliberately partial: libraries such as urllib3
    do `from ssl import (...)` inside try/except ImportError and so
    correctly conclude TLS is unavailable.
    """
    import sys
    import types

    try:
        import ssl  # pylint: disable=unused-import

        return  # Real ssl available; nothing to do.
    except ImportError:
        pass

    mod = types.ModuleType('ssl')
    mod.__doc__ = 'Stand-in ssl module for web builds (no TLS support).'

    class SSLError(OSError):
        """TLS is unavailable in web builds."""

    class SSLCertVerificationError(SSLError, ValueError):
        """Never raised; present for isinstance() checks."""

    class SSLContext:
        """Inert context; any attempt to wrap a socket fails."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def wrap_socket(self, *args: object, **kwargs: object) -> None:
            raise SSLError('TLS is not available in web builds.')

        def load_verify_locations(self, *args: object, **kw: object) -> None:
            del args, kw

        def load_default_certs(self, *args: object, **kw: object) -> None:
            del args, kw

    def create_default_context(*args: object, **kwargs: object) -> SSLContext:
        del args, kwargs
        return SSLContext()

    class _Inert:
        """Placeholder for ssl classes referenced at import time."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            raise SSLError('TLS is not available in web builds.')

    # Full exception hierarchy (stdlib modules such as asyncio.sslproto
    # reference these at import time).
    errors: dict[str, type] = {
        'SSLError': SSLError,
        'SSLCertVerificationError': SSLCertVerificationError,
        'CertificateError': SSLCertVerificationError,
    }
    for ename in (
        'SSLZeroReturnError',
        'SSLWantReadError',
        'SSLWantWriteError',
        'SSLSyscallError',
        'SSLEOFError',
    ):
        errors[ename] = type(ename, (SSLError,), {'__module__': 'ssl'})
    for ename, ecls in errors.items():
        setattr(mod, ename, ecls)

    for cname in ('SSLSocket', 'SSLObject', 'MemoryBIO', 'SSLSession'):
        setattr(mod, cname, type(cname, (_Inert,), {'__module__': 'ssl'}))

    mod.SSLContext = SSLContext  # type: ignore[attr-defined]
    mod.create_default_context = (  # type: ignore[attr-defined]
        create_default_context
    )
    mod._create_default_https_context = (  # type: ignore[attr-defined]
        create_default_context
    )
    mod.OPENSSL_VERSION = 'none (web build)'  # type: ignore[attr-defined]
    sys.modules['ssl'] = mod

    # urllib3 v2 warns at import that our 'ssl' isn't OpenSSL; expected.
    import warnings

    warnings.filterwarnings(
        'ignore', message=r'urllib3 v2 only supports OpenSSL'
    )


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
