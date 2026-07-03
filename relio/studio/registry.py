# relio/studio/registry.py
"""Project registry for Relio Studio.

Tracks the set of Relio projects a user has created or imported, persisting them
to `~/.relio/projects.json`. Also detects/scans folders for existing projects.
Pure filesystem logic — no FastAPI here, so it's trivially unit-testable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

# A Relio project is a directory with an `app.py` and a dependency manifest that
# references the framework. These are the manifests we inspect, in order.
_MANIFESTS = ("requirements.txt", "pyproject.toml")

# Best-effort kind inference from files a scaffold leaves behind.
_KIND_MARKERS = (
    ("mobile", ("app.json", "App.tsx")),   # Expo / React Native
    ("desktop", ("src-tauri",)),           # Tauri
    ("web", ("web/package.json",)),        # React + Vite
)


def default_registry_path() -> Path:
    """Where the registry lives by default: ``~/.relio/projects.json``."""
    return Path.home() / ".relio" / "projects.json"


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str
    path: str
    kind: str
    exists: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


def _project_id(resolved_path: Path) -> str:
    """A stable id derived from the resolved path, so the same folder always maps
    to the same id across restarts and is safe to use in URLs."""
    digest = hashlib.sha1(str(resolved_path).encode("utf-8")).hexdigest()
    return digest[:12]


def _references_relio(text: str) -> bool:
    return "relio" in text.lower()


def _infer_kind(path: Path) -> str:
    for kind, markers in _KIND_MARKERS:
        if all((path / m).exists() for m in markers):
            return kind
    return "app"


class Registry:
    """Reads/writes the Studio project registry file."""

    def __init__(self, path: Optional[Path | str] = None) -> None:
        self.path = Path(path) if path is not None else default_registry_path()

    # -- persistence -------------------------------------------------------
    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # -- detection ---------------------------------------------------------
    def detect(self, path: str | Path) -> Optional[str]:
        """Return the inferred kind if `path` looks like a Relio project, else None.

        A Relio project has an `app.py` and a manifest that references `relio`.
        """
        p = Path(path)
        if not (p / "app.py").is_file():
            return None
        for manifest in _MANIFESTS:
            mf = p / manifest
            if mf.is_file() and _references_relio(
                mf.read_text(encoding="utf-8", errors="ignore")
            ):
                return _infer_kind(p)
        return None

    def scan(self, folder: str | Path) -> list[str]:
        """Return resolved paths of Relio projects directly inside `folder`."""
        root = Path(folder)
        if not root.is_dir():
            return []
        found: list[str] = []
        for child in sorted(root.iterdir()):
            if child.is_dir() and self.detect(child) is not None:
                found.append(str(child.resolve()))
        return found

    # -- registry ops ------------------------------------------------------
    def add(self, path: str | Path, name: Optional[str] = None,
            kind: Optional[str] = None) -> ProjectRecord:
        resolved = Path(path).resolve()
        pid = _project_id(resolved)
        entries = self._read()
        rec = {
            "id": pid,
            "name": name or resolved.name,
            "path": str(resolved),
            "kind": kind or self.detect(resolved) or "app",
        }
        entries = [e for e in entries if e.get("id") != pid]  # dedupe by id/path
        entries.append(rec)
        self._write(entries)
        return ProjectRecord(**rec)

    def remove(self, project_id: str) -> bool:
        entries = self._read()
        kept = [e for e in entries if e.get("id") != project_id]
        if len(kept) == len(entries):
            return False
        self._write(kept)
        return True

    def get(self, project_id: str) -> Optional[ProjectRecord]:
        for rec in self.list():
            if rec.id == project_id:
                return rec
        return None

    def list(self) -> list[ProjectRecord]:
        out: list[ProjectRecord] = []
        for e in self._read():
            try:
                path = Path(e["path"])
                out.append(
                    ProjectRecord(
                        id=e["id"],
                        name=e.get("name", path.name),
                        path=e["path"],
                        kind=e.get("kind", "app"),
                        exists=path.is_dir(),
                    )
                )
            except KeyError:
                continue
        return out
