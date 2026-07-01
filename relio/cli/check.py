# relio/cli/check.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# The framework's quality gate: every source module must have a test and a doc.
_EXCLUDE_DIRS = {
    "tests",
    "docs",
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".claude",
    "sdk",
    ".pytest_cache",
}
_EXCLUDE_FILES = {"__init__.py"}
_SRC_SUFFIXES = {".py", ".ts", ".tsx"}
# Non-source files among those suffixes (tests, specs, configs, declarations).
_NON_SOURCE_MARKERS = (".test.", ".spec.", ".config.")


@dataclass(frozen=True)
class Violation:
    path: str
    missing: str  # "test" or "doc"


def _excluded(rel: Path) -> bool:
    return any(part in _EXCLUDE_DIRS for part in rel.parts)


def _read(f: Path) -> str:
    try:
        return f.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _is_source(p: Path, root: Path) -> bool:
    if p.suffix not in _SRC_SUFFIXES or not p.is_file():
        return False
    if p.name in _EXCLUDE_FILES or p.name.endswith(".d.ts"):
        return False
    if any(m in p.name for m in _NON_SOURCE_MARKERS):
        return False
    return not _excluded(p.relative_to(root))


def _iter_sources(root: Path):
    for p in root.rglob("*"):
        if _is_source(p, root):
            yield p


def _test_corpus(root: Path) -> str:
    """All text the gate accepts as evidence a module is tested."""
    files: list[Path] = []
    tests_dir = root / "tests"
    if tests_dir.exists():
        files += [f for f in tests_dir.rglob("*") if f.is_file()]
    for f in root.rglob("*"):
        if f.is_file() and any(m in f.name for m in (".test.", ".spec.")):
            if not _excluded(f.relative_to(root)):
                files.append(f)
    return "\n".join(_read(f) for f in files)


def _doc_corpus(root: Path) -> str:
    docs_dir = root / "docs"
    if not docs_dir.exists():
        return ""
    return "\n".join(_read(f) for f in docs_dir.rglob("*.md") if f.is_file())


def check_project(root: str | Path) -> list[Violation]:
    """Return a violation for every source module missing a test and/or a doc.

    Covers Python and TypeScript/React source. A module is "tested" if any test
    file references its stem, and "documented" if any docs/*.md references it.
    """
    root = Path(root)
    tests = _test_corpus(root)
    docs = _doc_corpus(root)
    violations: list[Violation] = []
    for src in _iter_sources(root):
        stem = src.stem
        rel = src.relative_to(root).as_posix()
        if not _references(tests, stem):
            violations.append(Violation(rel, "test"))
        if not _references(docs, stem):
            violations.append(Violation(rel, "doc"))
    return violations


def _references(corpus: str, stem: str) -> bool:
    """True if `stem` appears as a whole word (case-insensitive) — not a mere
    substring, so `car.py` isn't counted as tested just because "scary" appears."""
    return re.search(rf"\b{re.escape(stem)}\b", corpus, re.IGNORECASE) is not None
