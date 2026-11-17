from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from zfundpilot.desktop_backend import DesktopAccess


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
