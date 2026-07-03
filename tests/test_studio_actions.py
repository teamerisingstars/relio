# tests/test_studio_actions.py
import sys

import pytest

from relio.studio.actions import (
    ACTIONS,
    LONG_RUNNING,
    action_command,
    app_url,
)


def _relio(*args):
    return [sys.executable, "-m", "relio", *args]


def test_action_command_maps_simple_actions():
    assert action_command("build", {}) == _relio("build")
    assert action_command("test", {}) == _relio("test")
    assert action_command("dev", {}) == _relio("dev")
    assert action_command("dockerfile", {}) == _relio("dockerfile")


def test_serve_passes_port():
    assert action_command("serve", {"port": 9001}) == _relio("serve", "--port", "9001")


def test_deploy_passes_name_and_sdk_passes_out():
    assert action_command("deploy", {"name": "myimg"}) == _relio("deploy", "--name", "myimg")
    assert action_command("sdk", {"out": "sdk"}) == _relio("sdk", "--out", "sdk")


def test_deploy_passes_target():
    assert action_command("deploy", {"name": "myimg", "target": "fly"}) == \
        _relio("deploy", "--name", "myimg", "--target", "fly")


def test_install_action_pip_installs_requirements():
    assert action_command("install", {}) == [
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ]


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        action_command("nonsense", {})


def test_dev_and_serve_are_long_running():
    assert "dev" in LONG_RUNNING and "serve" in LONG_RUNNING
    assert "build" not in LONG_RUNNING
    assert LONG_RUNNING <= ACTIONS


def test_app_url_for_dev_and_serve():
    assert app_url("dev", {}) == "http://localhost:5173"
    assert app_url("serve", {"port": 9001}) == "http://localhost:9001"
    assert app_url("build", {}) is None
