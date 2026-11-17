import socket

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from zfundpilot.desktop_backend import HOST, DesktopAccess, bind_listener, lock_data_directory


def test_listener_uses_another_port_when_preferred_port_is_occupied():
    with socket.socket() as occupied, socket.socket() as listener:
        occupied.bind((HOST, 0))
        occupied.listen()
        preferred = occupied.getsockname()[1]
        bind_listener(listener, preferred)
        assert listener.getsockname()[0] == HOST
        assert listener.getsockname()[1] not in (0, preferred)


def test_listener_keeps_the_preferred_port_when_available():
    with socket.socket() as available:
        available.bind((HOST, 0))
        preferred = available.getsockname()[1]
    with socket.socket() as listener:
        bind_listener(listener, preferred)
        assert listener.getsockname() == (HOST, preferred)


def test_data_directory_lock_is_exclusive_and_released_on_close(tmp_path):
    with lock_data_directory(tmp_path):
        with pytest.raises(RuntimeError, match="已经在运行"):
            lock_data_directory(tmp_path)
    with lock_data_directory(tmp_path):
        pass


def test_desktop_backend_requires_a_one_time_bootstrap():
    async def index(_request):
        return PlainTextResponse("桌面页面")

    app = Starlette(routes=[Route("/", index, methods=["GET", "POST"])])
    app.add_middleware(DesktopAccess, port=48753, bootstrap="bootstrap-token")

    with TestClient(app, base_url="http://127.0.0.1:48753") as client:
        assert client.get("/").status_code == 403
        assert client.get("/_desktop/bootstrap-token").text == "桌面页面"
        assert client.get("/").status_code == 200
        assert client.get("/_desktop/bootstrap-token").status_code == 403
        assert client.post("/", headers={"Origin": "https://example.org"}).status_code == 403
        assert client.get("/", headers={"Host": "example.org"}).status_code == 403

    with TestClient(app, base_url="http://127.0.0.1:48753") as client:
        assert client.get("/").status_code == 403
