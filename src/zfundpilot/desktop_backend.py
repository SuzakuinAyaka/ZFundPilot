"""由桌面壳启动的本地后端。"""

import argparse
import errno
import os
import secrets
import socket
import sys
import threading
from pathlib import Path

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse
from uvicorn.protocols.http.h11_impl import H11Protocol

HOST = "127.0.0.1"
PORT = 48753
COOKIE = "zfundpilot_desktop"


class DesktopAccess(BaseHTTPMiddleware):
    """将回环端口上的页面和 API 限制在本次桌面会话内。"""

    def __init__(self, app, *, port, bootstrap):
        super().__init__(app)
        self.host = f"{HOST}:{port}"
        self.origin = f"http://{self.host}"
        self.bootstrap = f"/_desktop/{bootstrap}"
        self.session = secrets.token_urlsafe(32)

    async def dispatch(self, request, call_next):
        headers = request.headers
        if (
            headers.get("host") != self.host
            or headers.get("origin", self.origin) != self.origin
            or headers.get("sec-fetch-site") == "cross-site"
        ):
            return PlainTextResponse("Forbidden", status_code=403)

        if request.method == "GET" and request.url.path == self.bootstrap:
            self.bootstrap = None
            # 使用独立入口地址，绕过升级前 WebView 对根页面留下的缓存。
            response = RedirectResponse("/?desktop=1", status_code=303)
            response.set_cookie(COOKIE, self.session, httponly=True, samesite="strict")
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            return response

        session = request.cookies.get(COOKIE, "").encode()
        if not secrets.compare_digest(session, self.session.encode()):
            return PlainTextResponse("Forbidden", status_code=403)
        if request.url.path.startswith("/_desktop/"):
            return PlainTextResponse("Forbidden", status_code=403)
        response = await call_next(request)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-store"
        return response


def bind_listener(listener, preferred_port):
    if sys.platform == "win32":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)

    try:
        listener.bind((HOST, preferred_port))
    except OSError as error:
        # Windows 独占绑定冲突也可能报告 WSAEACCES（10013）。
        if not preferred_port or (
            error.errno != errno.EADDRINUSE and getattr(error, "winerror", None) not in (10013, 10048)
        ):
            raise
        listener.bind((HOST, 0))
        print(f"端口 {preferred_port} 无法绑定，已改用 {listener.getsockname()[1]}", file=sys.stderr)


def lock_data_directory(home):
    lock = (Path(home) / ".desktop.lock").open("a+b")
    try:
        if sys.platform == "win32":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        lock.close()
        if error.errno in (errno.EACCES, errno.EAGAIN):
            raise RuntimeError("ZFundPilot 已经在运行，请先关闭现有窗口。") from error
        raise
    return lock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--check-runtime", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.check_runtime:
        from py_mini_racer import MiniRacer

        with MiniRacer() as runtime:
            if runtime.eval("6 * 7") != 42:
                raise RuntimeError("MiniRacer 无法执行 JavaScript")
        return 0

    home = os.environ.get("ZFUNDPILOT_HOME")
    if not home:
        parser.error("ZFUNDPILOT_HOME is required")

    sys.stdout.reconfigure(encoding="utf-8")
    try:
        directory_lock = lock_data_directory(home)
    except RuntimeError as error:
        print(f"error:{error}", flush=True)
        return 1

    ready_output = sys.stdout
    sys.stdout = sys.stderr
    bootstrap = secrets.token_urlsafe(32)
    with directory_lock, socket.socket() as listener:
        bind_listener(listener, args.port)
        port = listener.getsockname()[1]

        from zfundpilot.api import app

        app.add_middleware(DesktopAccess, port=port, bootstrap=bootstrap)

        class Server(uvicorn.Server):
            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                if self.started:
                    print(f"http://{HOST}:{port}/_desktop/{bootstrap}", file=ready_output, flush=True)

        server = Server(uvicorn.Config(
            app, loop="asyncio", http=H11Protocol, ws="none", lifespan="on",
            proxy_headers=False, access_log=False, timeout_graceful_shutdown=5,
        ))

        def stop_when_shell_exits():
            sys.stdin.buffer.read()
            server.should_exit = True

        threading.Thread(target=stop_when_shell_exits, daemon=True).start()
        server.run(sockets=[listener])
        return 0 if server.started else 1


if __name__ == "__main__":
    sys.exit(main())
