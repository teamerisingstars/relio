from relio.server.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.model == "claude-opus-4-8"
    assert s.db_path == "relio.db"
    assert s.recall_limit == 5


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_server_exports_create_app():
    from relio import server

    assert hasattr(server, "create_app")
