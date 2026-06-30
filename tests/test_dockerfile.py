# tests/test_dockerfile.py
from relio.cli.dockerfile import render_dockerfile


def test_dockerfile_has_node_build_and_python_runtime():
    df = render_dockerfile()
    assert "FROM node" in df
    assert "npm run build" in df
    assert "FROM python" in df
    assert "uvicorn" in df
    assert "EXPOSE" in df
