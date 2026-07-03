# tests/test_deploytargets.py
from relio.cli.deploytargets import (
    SERVERLESS_TARGETS,
    TARGETS,
    files_for,
    render_fly_toml,
    render_hf_space,
    render_render_yaml,
    render_vercel_index,
    render_vercel_json,
)


def test_fly_toml_names_app_and_wires_port():
    toml = render_fly_toml("myapp", port=8000)
    assert 'app = "myapp"' in toml
    assert "internal_port = 8000" in toml
    assert "Dockerfile" in toml
    # Deploy needs these env knobs surfaced (as secrets).
    assert "DATABASE_URL" in toml
    assert "ANTHROPIC_API_KEY" in toml


def test_render_yaml_is_free_docker_web_service():
    y = render_render_yaml("myapp", port=8000)
    assert "name: myapp" in y
    assert "runtime: docker" in y
    assert "plan: free" in y
    assert "/api/health" in y
    assert "DATABASE_URL" in y


def test_hf_space_has_docker_sdk_frontmatter():
    md = render_hf_space("myapp", port=8000)
    assert md.startswith("---")
    assert "sdk: docker" in md
    assert "app_port: 8000" in md
    assert "title: myapp" in md


def test_targets_set():
    assert TARGETS == {"docker", "fly", "render", "hf", "vercel", "lambda", "netlify"}
    assert SERVERLESS_TARGETS == {"vercel", "lambda", "netlify"}


def test_files_for_returns_config_per_target():
    assert set(files_for("fly", "a", 8000)) == {"fly.toml"}
    assert set(files_for("render", "a", 8000)) == {"render.yaml"}
    assert set(files_for("hf", "a", 8000)) == {"README.md"}
    # docker uses the existing Dockerfile flow — no extra config files.
    assert files_for("docker", "a", 8000) == {}


def test_vercel_target_writes_asgi_entry_and_config():
    files = files_for("vercel", "a", 8000)
    assert set(files) == {"api/index.py", "vercel.json"}
    assert "app" in files["api/index.py"]           # exports the ASGI app
    assert "@vercel/python" in files["vercel.json"]


def test_vercel_index_imports_user_app():
    src = render_vercel_index()
    assert "from app import app" in src


def test_vercel_json_routes_everything_to_the_function():
    j = render_vercel_json("a")
    assert "api/index.py" in j
    assert "/(.*)" in j  # catch-all to the ASGI app (it serves the frontend too)


def test_lambda_target_uses_mangum():
    files = files_for("lambda", "a", 8000)
    assert set(files) == {"lambda_handler.py", "serverless.yml"}
    assert "Mangum" in files["lambda_handler.py"]
    assert "runtime: python" in files["serverless.yml"]


def test_netlify_target_is_static_plus_proxy():
    files = files_for("netlify", "a", 8000)
    assert set(files) == {"netlify.toml"}
    toml = files["netlify.toml"]
    assert "publish" in toml
    assert "/api/*" in toml  # proxy to an external backend
