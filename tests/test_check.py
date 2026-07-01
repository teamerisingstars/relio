# tests/test_check.py
from relio.cli.check import check_project


def _clean_project(root):
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    (root / "app.py").write_text("x = 1\n")
    (root / "tests" / "test_app.py").write_text("import app  # references app\n")
    (root / "docs" / "app.md").write_text("# app\n")


def test_clean_project_has_no_violations(tmp_path):
    _clean_project(tmp_path)
    assert check_project(tmp_path) == []


def test_missing_doc_is_flagged(tmp_path):
    _clean_project(tmp_path)
    (tmp_path / "docs" / "app.md").unlink()
    v = check_project(tmp_path)
    assert [(x.path, x.missing) for x in v] == [("app.py", "doc")]


def test_missing_test_is_flagged(tmp_path):
    _clean_project(tmp_path)
    (tmp_path / "tests" / "test_app.py").unlink()
    v = check_project(tmp_path)
    assert [(x.path, x.missing) for x in v] == [("app.py", "test")]


def test_init_and_excluded_dirs_are_ignored(tmp_path):
    _clean_project(tmp_path)
    (tmp_path / "__init__.py").write_text("")  # ignored
    (tmp_path / "sdk").mkdir()
    (tmp_path / "sdk" / "client.py").write_text("y = 2\n")  # excluded dir
    assert check_project(tmp_path) == []


def test_substring_only_match_is_not_counted_as_tested(tmp_path):
    # Tightened gate: whole-word match. "scary" contains "car" as a substring
    # but does not reference the `car` module, so it must still be flagged.
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "car.py").write_text("x = 1\n")
    (tmp_path / "tests" / "test_misc.py").write_text("# a scary edge case\n")
    (tmp_path / "docs" / "misc.md").write_text("# scary things\n")
    missing = {(v.path, v.missing) for v in check_project(tmp_path)}
    assert ("car.py", "test") in missing
    assert ("car.py", "doc") in missing

    # a real whole-word reference satisfies it
    (tmp_path / "tests" / "test_car.py").write_text("import car  # references car\n")
    (tmp_path / "docs" / "car.md").write_text("# car\n")
    assert check_project(tmp_path) == []


def test_typescript_component_is_gated(tmp_path):
    _clean_project(tmp_path)
    web = tmp_path / "web" / "src"
    web.mkdir(parents=True)
    (web / "ChatView.tsx").write_text("export function ChatView() { return null; }\n")
    # missing both a test and a doc for ChatView
    missing = {(v.path, v.missing) for v in check_project(tmp_path)}
    assert ("web/src/ChatView.tsx", "test") in missing
    assert ("web/src/ChatView.tsx", "doc") in missing

    # add a co-located test + a doc → satisfied
    (web / "ChatView.test.tsx").write_text("test('ChatView present', () => {});\n")
    (tmp_path / "docs" / "ChatView.md").write_text("# ChatView\n")
    assert check_project(tmp_path) == []


def test_generated_sdk_and_declaration_files_are_excluded(tmp_path):
    _clean_project(tmp_path)
    sdk = tmp_path / "web" / "src" / "sdk"
    sdk.mkdir(parents=True)
    (sdk / "client.ts").write_text("export class C {}\n")  # excluded (sdk dir)
    (tmp_path / "web" / "src" / "vite-env.d.ts").write_text("// types\n")  # .d.ts
    assert check_project(tmp_path) == []
