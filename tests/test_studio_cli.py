# tests/test_studio_cli.py
import sys

from relio.cli.main import build_parser, main


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd, cwd=None):
        self.calls.append(cmd)
        return 0


def test_parser_recognizes_gui():
    parser = build_parser()
    args = parser.parse_args(["gui"])
    assert args.command == "gui"
    assert args.port == 4000  # default
    assert parser.parse_args(["gui", "--port", "4100"]).port == 4100
    assert parser.parse_args(["gui", "--no-open"]).no_open is True


def test_gui_launches_uvicorn_on_studio_app():
    runner = FakeRunner()
    rc = main(["gui", "--no-open", "--port", "4100"], runner=runner)
    assert rc == 0
    cmd = runner.calls[0]
    assert sys.executable in cmd
    assert "uvicorn" in cmd
    assert "relio.studio.launch:app" in cmd
    assert "4100" in cmd


def test_gui_without_server_extra_gives_hint(monkeypatch, capsys):
    monkeypatch.setattr("relio.cli.main._missing_server_extra", lambda: True)
    rc = main(["gui", "--no-open"], runner=FakeRunner())
    assert rc == 1
    assert "relio[server]" in capsys.readouterr().err


def test_launch_module_exposes_app():
    import fastapi  # noqa: F401

    from relio.studio.launch import app

    assert app.title == "Relio Studio"
