"""在独立数据目录验证打包产物的页面、接口和退出。"""

import os
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin, urlsplit

import httpx


def verify_backend(executable, home, occupied_port):
    command = [str(executable), "--port", str(occupied_port)]
    environment = {**os.environ, "ZFUNDPILOT_HOME": str(home)}
    with (home / "backend.log").open("w+b") as log:
        with subprocess.Popen(
            command,
            cwd=home,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            encoding="utf-8",
        ) as backend, ThreadPoolExecutor(max_workers=1) as pool:
            try:
                url = pool.submit(backend.stdout.readline).result(timeout=45).strip()
                assert url.startswith("http://127.0.0.1:"), "后端未返回就绪地址"
                assert urlsplit(url).port != occupied_port, "后端未回退到空闲端口"
                with httpx.Client(follow_redirects=True, trust_env=False) as client:
                    assert client.get(urljoin(url, "/api/auth/status")).status_code == 403
                    page = client.get(url)
                    page.raise_for_status()
                    script = re.search(r'<script[^>]+src="([^"]+)"', page.text)
                    assert script, "生产首页缺少前端构建产物"
                    client.get(urljoin(url, script[1])).raise_for_status()
                    client.get(urljoin(url, "/api/auth/status")).raise_for_status()
                assert (home / "data" / "fund.db").is_file()
                duplicate = subprocess.run(
                    command, cwd=home, env=environment, input="", capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=15,
                )
                assert duplicate.returncode == 1 and "已经在运行" in duplicate.stdout
                backend.stdin.close()
                assert backend.wait(timeout=15) == 0
            except Exception:
                log.seek(0)
                print(log.read().decode("utf-8", errors="replace"), file=sys.stderr)
                raise
            finally:
                if backend.poll() is None:
                    backend.kill()


if __name__ == "__main__":
    with TemporaryDirectory(prefix="zfundpilot-smoke-") as directory, socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        verify_backend(Path(sys.argv[1]).resolve(), Path(directory), occupied.getsockname()[1])
    print("桌面后端冒烟验证通过")
