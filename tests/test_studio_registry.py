# tests/test_studio_registry.py
from pathlib import Path

from relio.studio.registry import ProjectRecord, Registry


def _make_project(root: Path, name: str, *, marker: str = "relio") -> Path:
    proj = root / name
    proj.mkdir(parents=True)
    (proj / "app.py").write_text("# app\n", encoding="utf-8")
    (proj / "requirements.txt").write_text(f"{marker}\n", encoding="utf-8")
    return proj


def test_add_persists_project_and_assigns_stable_id(tmp_path):
    reg_file = tmp_path / "projects.json"
    proj = _make_project(tmp_path, "alpha")

    reg = Registry(reg_file)
    rec = reg.add(str(proj))
    assert isinstance(rec, ProjectRecord)
    assert rec.name == "alpha"

    # A fresh Registry reading the same file sees the persisted project with the
    # same id (id is a stable hash of the resolved path).
    reloaded = Registry(reg_file).list()
    assert len(reloaded) == 1
    assert reloaded[0].id == rec.id
    assert Path(reloaded[0].path) == proj.resolve()


def test_add_is_idempotent_by_resolved_path(tmp_path):
    proj = _make_project(tmp_path, "beta")
    reg = Registry(tmp_path / "projects.json")
    reg.add(str(proj))
    reg.add(str(proj) + "/")  # same path, trailing slash
    assert len(reg.list()) == 1


def test_list_flags_missing_when_folder_gone(tmp_path):
    proj = _make_project(tmp_path, "gamma")
    reg = Registry(tmp_path / "projects.json")
    reg.add(str(proj))
    # Remove the folder on disk; the registry entry should be flagged missing.
    (proj / "app.py").unlink()
    (proj / "requirements.txt").unlink()
    proj.rmdir()
    rec = reg.list()[0]
    assert rec.exists is False


def test_remove_drops_entry_but_not_files(tmp_path):
    proj = _make_project(tmp_path, "delta")
    reg = Registry(tmp_path / "projects.json")
    rec = reg.add(str(proj))
    reg.remove(rec.id)
    assert reg.list() == []
    assert (proj / "app.py").exists()  # files untouched


def test_detect_identifies_relio_projects(tmp_path):
    proj = _make_project(tmp_path, "epsilon")
    not_proj = tmp_path / "plain"
    not_proj.mkdir()
    (not_proj / "app.py").write_text("# app\n", encoding="utf-8")
    (not_proj / "requirements.txt").write_text("flask\n", encoding="utf-8")

    reg = Registry(tmp_path / "projects.json")
    assert reg.detect(str(proj)) is not None
    assert reg.detect(str(not_proj)) is None  # no relio dependency


def test_detect_reads_pyproject_when_no_requirements(tmp_path):
    proj = tmp_path / "zeta"
    proj.mkdir()
    (proj / "app.py").write_text("# app\n", encoding="utf-8")
    (proj / "pyproject.toml").write_text('dependencies = ["relio[server]"]\n', encoding="utf-8")
    reg = Registry(tmp_path / "projects.json")
    assert reg.detect(str(proj)) is not None


def test_scan_finds_projects_one_level_down(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _make_project(workspace, "one")
    _make_project(workspace, "two")
    (workspace / "random").mkdir()  # not a project

    reg = Registry(tmp_path / "projects.json")
    found = reg.scan(str(workspace))
    names = sorted(Path(p).name for p in found)
    assert names == ["one", "two"]
