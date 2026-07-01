# tests/test_cli.py
import sys

from relio.cli.main import build_parser, main


def _is_npm(exe):
    low = exe.lower()
    return low == "npm" or low.endswith("npm.cmd") or low.endswith(("/npm", "\\npm"))


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        return 0


class FakeProc:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True


class FakeSpawn:
    def __init__(self):
        self.calls = []
        self.proc = FakeProc()

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        return self.proc


def test_python_m_relio_entrypoint_exists():
    # `python -m relio` must work — there should be a relio/__main__.py that
    # dispatches to the same CLI as the console script.
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "relio", "--help"], capture_output=True, text=True
    )
    assert out.returncode == 0
    assert "relio" in out.stdout.lower()


def test_parser_recognizes_subcommands():
    parser = build_parser()
    assert parser.parse_args(["new", "myapp"]).command == "new"
    assert parser.parse_args(["new", "myapp"]).name == "myapp"
    assert parser.parse_args(["serve", "--port", "9000"]).port == 9000
    for c in ("dev", "build", "dockerfile", "deploy"):
        assert parser.parse_args([c]).command == c


def test_migrate_copies_a_store_between_sqlite_files(tmp_path, capsys):
    from relio.backends.sqlite import SQLiteBackend
    from relio.record import MemoryRecord

    src_path = str(tmp_path / "src.db")
    dst_path = str(tmp_path / "dst.db")
    src = SQLiteBackend(src_path, dim=384)
    src.add(MemoryRecord(content="hello"), None)
    src.close()

    # --no-embed avoids the fastembed dependency in tests.
    assert main(["migrate", "--from", src_path, "--to", dst_path, "--no-embed"]) == 0
    assert "migrated 1 records" in capsys.readouterr().out
    assert len(SQLiteBackend(dst_path, dim=384).all()) == 1


def test_build_runs_npm():
    runner = FakeRunner()
    assert main(["build"], runner=runner) == 0
    # targets the scaffolded app's web/ dir, not the framework's frontend/;
    # npm is resolved (npm.cmd on Windows) so it doesn't WinError-2.
    (cmd,) = runner.calls
    assert _is_npm(cmd[0]) and cmd[1:] == ["--prefix", "web", "run", "build"]


def test_serve_runs_uvicorn_on_the_port():
    runner = FakeRunner()
    main(["serve", "--port", "9000"], runner=runner)
    # runs via `sys.executable -m uvicorn` so it resolves inside the venv
    assert runner.calls == [
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
    ]


def test_deploy_builds_the_docker_image():
    runner = FakeRunner()
    main(["deploy"], runner=runner)
    assert runner.calls == [["docker", "build", "-t", "relio-app", "."]]


def test_deploy_custom_image_name():
    runner = FakeRunner()
    main(["deploy", "--name", "myimg"], runner=runner)
    assert runner.calls == [["docker", "build", "-t", "myimg", "."]]


def test_dev_starts_backend_and_frontend_then_stops_backend():
    runner = FakeRunner()
    spawner = FakeSpawn()
    main(["dev"], runner=runner, spawner=spawner)
    assert spawner.calls == [[sys.executable, "-m", "uvicorn", "app:app", "--reload"]]
    (cmd,) = runner.calls
    assert _is_npm(cmd[0]) and cmd[1:] == ["--prefix", "web", "run", "dev"]
    assert spawner.proc.terminated is True


def test_dockerfile_writes_a_dockerfile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["dockerfile"], runner=FakeRunner())
    assert (tmp_path / "Dockerfile").is_file()
    assert "uvicorn" in (tmp_path / "Dockerfile").read_text()


def test_new_scaffolds_an_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "myapp"], runner=FakeRunner())
    assert (tmp_path / "myapp" / "app.py").is_file()


def test_new_web_scaffolds_a_react_app_with_sdk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "webapp", "--web"], runner=FakeRunner())
    assert (tmp_path / "webapp" / "web" / "package.json").is_file()
    assert (tmp_path / "webapp" / "web" / "src" / "sdk" / "client.ts").is_file()
    # vite/client ambient types — without this, `tsc` fails on the CSS import
    assert (tmp_path / "webapp" / "web" / "src" / "vite-env.d.ts").is_file()


def test_new_mobile_and_desktop_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "m", "--mobile"], runner=FakeRunner())
    assert (tmp_path / "m" / "App.tsx").is_file()
    assert (tmp_path / "m" / "src" / "sdk" / "client.ts").is_file()

    main(["new", "d", "--desktop"], runner=FakeRunner())
    assert (tmp_path / "d" / "src-tauri" / "tauri.conf.json").is_file()
    assert (tmp_path / "d" / "src" / "sdk" / "client.ts").is_file()


def test_develop_invokes_claude_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = FakeRunner()
    main(["develop", "add a contacts page"], runner=runner)
    assert runner.calls == [["claude", "-p", "add a contacts page"]]


def test_test_command_runs_pytest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = FakeRunner()
    main(["test"], runner=runner)
    # `sys.executable -m pytest`, not a bare "pytest" (WinError 2 on Windows)
    assert runner.calls == [[sys.executable, "-m", "pytest"]]


def test_test_coverage_enforces_threshold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = FakeRunner()
    main(["test", "--coverage", "--min", "90"], runner=runner)
    assert runner.calls == [[sys.executable, "-m", "pytest", "--cov=.", "--cov-fail-under=90"]]


def test_develop_feeds_check_violations_to_claude(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # a source module with no test/doc -> a gap the develop prompt should carry
    (tmp_path / "service.py").write_text("x = 1\n")
    runner = FakeRunner()
    main(["develop", "add billing"], runner=runner)
    assert len(runner.calls) == 1
    cmd = runner.calls[0]
    assert cmd[0] == "claude" and cmd[1] == "-p"
    prompt = cmd[2]
    assert "add billing" in prompt
    assert "service.py missing" in prompt


def test_check_passes_on_a_fresh_scaffold(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["new", "myapp"], runner=FakeRunner())
    monkeypatch.chdir(tmp_path / "myapp")
    rc = main(["check"], runner=FakeRunner())
    assert rc == 0  # a fresh scaffold satisfies its own gate


def test_ai_new_scaffolds_an_ai_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["ai", "new", "assistant"], runner=FakeRunner())
    app_py = tmp_path / "assistant" / "app.py"
    assert app_py.is_file()
    assert "AIApp" in app_py.read_text()
    assert "relio[ai]" in (tmp_path / "assistant" / "requirements.txt").read_text()
    # the AI-app scaffold also satisfies the governance gate
    from relio.cli.check import check_project

    assert check_project(tmp_path / "assistant") == []
