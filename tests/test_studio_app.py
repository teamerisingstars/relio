# tests/test_studio_app.py
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from relio.studio.app import create_studio_app  # noqa: E402
from relio.studio.registry import Registry  # noqa: E402


class FakeManager:
    """Records start/stop calls; serves canned logs/status."""

    def __init__(self):
        self.started = []
        self.stopped = []
        self._logs = {}

    def start(self, project_id, action, cmd, cwd=None):
        self.started.append((project_id, action, cmd, cwd))

    def stop(self, project_id, action):
        self.stopped.append((project_id, action))
        return True

    def logs(self, project_id, action, since=0):
        return (2, self._logs.get((project_id, action), ["line-a", "line-b"]))

    def status(self, project_id):
        return {a: {"running": True, "returncode": None, "pid": 1}
                for (p, a) in self.started if p == project_id}


@pytest.fixture
def client(tmp_path):
    reg = Registry(tmp_path / "projects.json")
    mgr = FakeManager()
    app = create_studio_app(registry=reg, manager=mgr)
    c = TestClient(app)
    c.registry = reg
    c.manager = mgr
    c.workspace = tmp_path
    return c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_project_scaffolds_and_registers(client):
    parent = client.workspace / "made"
    resp = client.post("/api/projects", json={
        "name": "myapp", "parent_dir": str(parent), "kind": "app",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "myapp"
    # Scaffold actually wrote the project on disk...
    assert (parent / "myapp" / "app.py").exists()
    # ...and it's registered.
    assert any(p.name == "myapp" for p in client.registry.list())


def test_list_projects_returns_registered(client):
    proj = client.workspace / "existing"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    client.registry.add(str(proj))
    listed = client.get("/api/projects").json()
    assert len(listed) == 1
    assert listed[0]["name"] == "existing"


def test_import_existing_project(client):
    proj = client.workspace / "imp"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    resp = client.post("/api/projects/import", json={"path": str(proj)})
    assert resp.status_code == 200
    assert any(p.name == "imp" for p in client.registry.list())


def test_scan_folder_returns_detected(client):
    ws = client.workspace / "scanme"
    for n in ("a", "b"):
        p = ws / n
        p.mkdir(parents=True)
        (p / "app.py").write_text("# app\n")
        (p / "requirements.txt").write_text("relio\n")
    resp = client.post("/api/projects/scan", json={"folder": str(ws)})
    assert resp.status_code == 200
    assert len(resp.json()["found"]) == 2


def test_delete_unregisters_project(client):
    proj = client.workspace / "gone"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    rec = client.registry.add(str(proj))
    resp = client.delete(f"/api/projects/{rec.id}")
    assert resp.status_code == 200
    assert client.registry.list() == []


def test_start_action_invokes_manager(client):
    proj = client.workspace / "run"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    rec = client.registry.add(str(proj))
    resp = client.post(f"/api/projects/{rec.id}/actions/serve", json={"port": 9001})
    assert resp.status_code == 200
    assert resp.json()["url"] == "http://localhost:9001"
    pid, action, cmd, cwd = client.manager.started[0]
    assert action == "serve"
    assert cmd[-2:] == ["--port", "9001"]
    assert cwd == rec.path


def test_start_unknown_action_is_400(client):
    proj = client.workspace / "run2"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    rec = client.registry.add(str(proj))
    resp = client.post(f"/api/projects/{rec.id}/actions/bogus", json={})
    assert resp.status_code == 400


def test_stop_action(client):
    proj = client.workspace / "stop"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    rec = client.registry.add(str(proj))
    resp = client.post(f"/api/projects/{rec.id}/stop/serve")
    assert resp.status_code == 200
    assert client.manager.stopped == [(rec.id, "serve")]


def test_logs_endpoint_returns_lines(client):
    proj = client.workspace / "logs"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n")
    (proj / "requirements.txt").write_text("relio\n")
    rec = client.registry.add(str(proj))
    resp = client.get(f"/api/projects/{rec.id}/logs/serve?since=0")
    body = resp.json()
    assert body["lines"] == ["line-a", "line-b"]
    assert body["next"] == 2


def test_check_endpoint_returns_violations(client):
    # A real scaffolded project satisfies the gate → no violations.
    from relio.cli.scaffold import write_scaffold

    proj = client.workspace / "checked"
    write_scaffold(str(proj), "checked")
    rec = client.registry.add(str(proj))
    resp = client.get(f"/api/projects/{rec.id}/check")
    assert resp.status_code == 200
    assert resp.json()["violations"] == []


def test_action_on_unknown_project_is_404(client):
    resp = client.post("/api/projects/deadbeef/actions/serve", json={})
    assert resp.status_code == 404


def test_api_requires_token_when_set(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<head></head><body></body>", encoding="utf-8")
    app = create_studio_app(
        registry=Registry(tmp_path / "r.json"), manager=FakeManager(),
        web_dir=str(web), token="s3cret",
    )
    c = TestClient(app, base_url="http://127.0.0.1")
    assert c.get("/api/health").status_code == 403  # no token
    ok = c.get("/api/health", headers={"X-Relio-Studio-Token": "s3cret"})
    assert ok.status_code == 200
    # The served page injects the token so the SPA can authenticate.
    assert "s3cret" in c.get("/").text


def test_api_rejects_non_loopback_host_when_hardened(tmp_path):
    # DNS-rebinding defense: a request whose Host isn't loopback is refused.
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<head></head>", encoding="utf-8")
    app = create_studio_app(
        registry=Registry(tmp_path / "r.json"), manager=FakeManager(),
        web_dir=str(web), token="s3cret",
    )
    c = TestClient(app, base_url="http://evil.example.com")
    resp = c.get("/api/health", headers={"X-Relio-Studio-Token": "s3cret"})
    assert resp.status_code == 403


def test_studio_blocks_path_traversal(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>Studio</h1>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    app = create_studio_app(
        registry=Registry(tmp_path / "r.json"), manager=FakeManager(), web_dir=str(web)
    )
    c = TestClient(app)
    for attack in ("/..%2fsecret.txt", "/%2e%2e/secret.txt"):
        assert "TOP-SECRET" not in c.get(attack).text, f"leaked via {attack}"


def test_static_index_served(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>Relio Studio</h1>", encoding="utf-8")
    app = create_studio_app(
        registry=Registry(tmp_path / "r.json"), manager=FakeManager(), web_dir=str(web)
    )
    resp = TestClient(app).get("/")
    assert "Relio Studio" in resp.text
