"""由桌面壳启动的本地后端。"""

import argparse
import os
import secrets
import socket
import sys
import threading

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
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(COOKIE, self.session, httponly=True, samesite="strict")
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            return response

        session = request.cookies.get(COOKIE, "").encode()
        if not secrets.compare_digest(session, self.session.encode()):
            return PlainTextResponse("Forbidden", status_code=403)
        if request.url.path.startswith("/_desktop/"):
            return PlainTextResponse("Forbidden", status_code=403)
        return await call_next(request)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    if not os.environ.get("ZFUNDPILOT_HOME"):
        parser.error("ZFUNDPILOT_HOME is required")

    ready_output = sys.stdout
    sys.stdout = sys.stderr
    bootstrap = secrets.token_urlsafe(32)
    with socket.socket() as listener:
        if sys.platform == "win32":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((HOST, args.port))
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
