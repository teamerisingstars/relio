# tests/test_scaffold.py
from relio.cli.scaffold import write_scaffold


def test_scaffold_creates_runnable_starter(tmp_path):
    root = write_scaffold(str(tmp_path / "myapp"), "myapp")
    assert (root / "app.py").is_file()
    assert (root / "web" / "index.html").is_file()
    assert (root / "Dockerfile").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "README.md").is_file()

    assert "create_app" in (root / "app.py").read_text()
    index = (root / "web" / "index.html").read_text()
    assert "myapp" in index and "/api/chat" in index
    assert "relio[server]" in (root / "requirements.txt").read_text()
    assert "uvicorn" in (root / "Dockerfile").read_text()
