# tests/test_framework_fixes.py
# Regressions for friction reported while building apps on Relio
# (relio-framework-feedback).
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from relio.embedding.base import DeterministicEmbedder
from relio.memory import Memory
from relio.record import Scope
from relio.server.app import create_app
from relio.server.auth import JWTAuth
from relio.server.llm.fake import FakeProvider

SECRET = "a-long-test-secret-at-least-32-bytes-long!!"


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "f.db"), embedder=DeterministicEmbedder(dim=16))


def test_auth_hook_works_as_fastapi_dependency():
    # Before the fix, stringized annotations made `Depends(JWTAuth(...))` treat
    # `request` as a query param -> auth never enforced (422). Now: real 401.
    app = FastAPI()
    auth = JWTAuth(SECRET)

    @app.get("/protected")
    def protected(scope: Scope = Depends(auth)):
        return {"user": scope.user}

    client = TestClient(app)
    assert client.get("/protected").status_code == 401  # enforced, not 422


def test_extra_routers_are_not_shadowed_by_spa(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("INDEX", encoding="utf-8")

    router = APIRouter()

    @router.get("/custom")
    def custom():
        return {"ok": True}

    m = _mem(tmp_path)
    app = create_app(m, FakeProvider(), extra_routers=[router], frontend_dir=str(dist))
    client = TestClient(app)
    assert client.get("/custom").json() == {"ok": True}   # not shadowed by index.html
    m.close()


def test_scaffolded_test_file_is_valid_utf8_python(tmp_path):
    # The scaffold's tests/test_app.py contains an em-dash; it must be written as
    # UTF-8 so Python can parse it (regression: `\x97` SyntaxError on Windows).
    from relio.cli.scaffold import write_scaffold

    root = write_scaffold(str(tmp_path / "app"), "app")
    test_file = root / "tests" / "test_app.py"
    text = test_file.read_text(encoding="utf-8")   # must decode as UTF-8
    compile(text, str(test_file), "exec")          # must parse
