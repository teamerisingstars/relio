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


def test_scaffold_includes_dev_harness_and_passes_check(tmp_path):
    from relio.cli.check import check_project

    root = write_scaffold(str(tmp_path / "app1"), "app1")
    assert (root / "CLAUDE.md").is_file()
    assert (root / "docs" / "README.md").is_file()
    assert (root / "docs" / "app.md").is_file()
    assert (root / "tests" / "test_app.py").is_file()
    assert (root / ".claude" / "settings.json").is_file()
    assert "relio check" in (root / ".claude" / "settings.json").read_text()
    # a fresh scaffold satisfies its own governance gate
    assert check_project(root) == []


def test_web_scaffold_passes_governance_check(tmp_path):
    from relio.cli.check import check_project

    root = write_scaffold(str(tmp_path / "app2"), "app2", web=True)
    assert (root / "CLAUDE.md").is_file()
    assert check_project(root) == []


def test_web_scaffold_creates_react_app_with_generated_sdk(tmp_path):
    root = write_scaffold(str(tmp_path / "webapp"), "webapp", web=True)
    assert (root / "app.py").is_file()
    assert 'frontend_dir="web/dist"' in (root / "app.py").read_text()

    # React template copied in
    assert (root / "web" / "package.json").is_file()
    assert (root / "web" / "src" / "App.tsx").is_file()
    assert (root / "web" / "vite.config.ts").is_file()

    # SDK generated next to the components that import it
    types = (root / "web" / "src" / "sdk" / "types.ts").read_text()
    client = (root / "web" / "src" / "sdk" / "client.ts").read_text()
    assert "export interface MemoryRecord" in types
    assert "class RelioClient" in client

    # multi-stage Dockerfile builds the web app then serves it
    df = (root / "Dockerfile").read_text()
    assert "node:" in df and "npm run build" in df


def test_mobile_scaffold_creates_expo_app_with_sdk(tmp_path):
    root = write_scaffold(str(tmp_path / "m"), "m", mobile=True)
    assert (root / "App.tsx").is_file()
    pkg = (root / "package.json").read_text()
    assert "expo" in pkg
    assert "react-native" in pkg
    assert "class RelioClient" in (root / "src" / "sdk" / "client.ts").read_text()


def test_desktop_scaffold_creates_tauri_app_with_sdk(tmp_path):
    root = write_scaffold(str(tmp_path / "d"), "d", desktop=True)
    # web UI reused
    assert (root / "src" / "App.tsx").is_file()
    # tauri shell overlaid
    assert (root / "src-tauri" / "tauri.conf.json").is_file()
    assert (root / "src-tauri" / "Cargo.toml").is_file()
    assert "@tauri-apps/cli" in (root / "package.json").read_text()
    # generated SDK
    assert "class RelioClient" in (root / "src" / "sdk" / "client.ts").read_text()
