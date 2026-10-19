import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from autosub.web import files
from autosub.web.server import create_server


@pytest.fixture
def server(tmp_path: Path):
    srv = create_server(port=0, queue_file=tmp_path / "queue.json")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def request(url: str, body: dict | None = None, headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def test_serves_page_and_state(server):
    status, page = request(server + "/")
    assert status == 200 and b"AutoSub" in page
    status, body = request(server + "/api/state")
    assert status == 200 and json.loads(body)["jobs"] == []


def test_rejects_foreign_host_header(server):
    status, _ = request(server + "/api/state", headers={"Host": "evil.example"})
    assert status == 403


def test_mkdir_and_scan(server, tmp_path: Path):
    target = tmp_path / "Show" / "Season 1"
    status, _ = request(server + "/api/mkdir", {"path": str(target)})
    assert status == 200 and target.is_dir()
    (target / "E01.mkv").write_bytes(b"")
    result = files.scan(str(tmp_path / "Show"))
    assert result["videos"] == 0
    assert result["seasons"] == [{"name": "Season 1", "path": str(target), "videos": 1}]


def test_bad_requests(server):
    assert request(server + "/api/nope")[0] == 404
    assert request(server + "/api/jobs", {"input": "/does/not/exist", "output": "/tmp/x"})[0] == 400
    assert request(server + "/api/jobs", {})[0] == 400
