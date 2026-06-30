# tests/test_cli.py
from relio.cli.main import build_parser, main


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


def test_parser_recognizes_subcommands():
    parser = build_parser()
    assert parser.parse_args(["new", "myapp"]).command == "new"
    assert parser.parse_args(["new", "myapp"]).name == "myapp"
    assert parser.parse_args(["serve", "--port", "9000"]).port == 9000
    for c in ("dev", "build", "dockerfile", "deploy"):
        assert parser.parse_args([c]).command == c


def test_build_runs_npm():
    runner = FakeRunner()
    assert main(["build"], runner=runner) == 0
    assert runner.calls == [["npm", "--prefix", "frontend", "run", "build"]]


def test_serve_runs_uvicorn_on_the_port():
    runner = FakeRunner()
    main(["serve", "--port", "9000"], runner=runner)
    assert runner.calls == [
        ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
    ]


def test_deploy_builds_the_docker_image():
    runner = FakeRunner()
    main(["deploy"], runner=runner)
    assert runner.calls == [["docker", "build", "-t", "relio-app", "."]]


def test_dev_starts_backend_and_frontend_then_stops_backend():
    runner = FakeRunner()
    spawner = FakeSpawn()
    main(["dev"], runner=runner, spawner=spawner)
    assert spawner.calls == [["uvicorn", "app:app", "--reload"]]
    assert runner.calls == [["npm", "--prefix", "frontend", "run", "dev"]]
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
