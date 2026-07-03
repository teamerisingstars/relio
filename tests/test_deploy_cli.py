# tests/test_deploy_cli.py
from relio.cli.main import build_parser, main


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        return 0


def test_parser_target_defaults_to_docker():
    parser = build_parser()
    assert parser.parse_args(["deploy"]).target == "docker"
    assert parser.parse_args(["deploy", "--target", "fly"]).target == "fly"


def test_deploy_docker_still_builds_image(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("relio.cli.main.shutil.which", lambda _: "/usr/bin/docker")
    runner = FakeRunner()
    assert main(["deploy"], runner=runner) == 0
    assert runner.calls == [["docker", "build", "-t", "relio-app", "."]]


def test_deploy_fly_writes_config_and_dockerfile(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    runner = FakeRunner()
    assert main(["deploy", "--target", "fly", "--name", "coolapp"], runner=runner) == 0
    # No docker build for a config-only target.
    assert runner.calls == []
    fly = (tmp_path / "fly.toml")
    assert fly.is_file()
    assert 'app = "coolapp"' in fly.read_text()
    # A Dockerfile is ensured so the platform has something to build.
    assert (tmp_path / "Dockerfile").is_file()


def test_deploy_render_writes_blueprint(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["deploy", "--target", "render"], runner=FakeRunner()) == 0
    assert "runtime: docker" in (tmp_path / "render.yaml").read_text()


def test_deploy_vercel_writes_nested_entry_no_dockerfile(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["deploy", "--target", "vercel"], runner=FakeRunner()) == 0
    assert (tmp_path / "api" / "index.py").is_file()   # nested path created
    assert (tmp_path / "vercel.json").is_file()
    # Serverless targets don't build from a Dockerfile.
    assert not (tmp_path / "Dockerfile").exists()


def test_deploy_lambda_writes_handler_and_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["deploy", "--target", "lambda"], runner=FakeRunner()) == 0
    assert "Mangum" in (tmp_path / "lambda_handler.py").read_text()
    assert (tmp_path / "serverless.yml").is_file()


def test_deploy_netlify_writes_toml(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["deploy", "--target", "netlify"], runner=FakeRunner()) == 0
    assert "publish" in (tmp_path / "netlify.toml").read_text()


def test_deploy_hf_does_not_clobber_existing_readme(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("ORIGINAL", encoding="utf-8")
    assert main(["deploy", "--target", "hf"], runner=FakeRunner()) == 0
    # Existing README is preserved (frontmatter is printed as guidance instead).
    assert (tmp_path / "README.md").read_text() == "ORIGINAL"
