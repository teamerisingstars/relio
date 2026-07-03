# relio/studio/process.py
"""Run and track commands for Relio Studio, streaming their output.

`ProcessManager` spawns child processes (via an injectable spawner so tests need
no real processes), keeps them keyed by ``(project_id, action)``, and buffers
their output line-by-line for late-joining log viewers (the SSE endpoint).

Handles both long-lived actions (``dev``/``serve``) and one-shot ones
(``build``/``test``/...) — the difference is only whether the process exits.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from typing import Callable, Optional

# spawner(cmd, cwd) -> process with .stdout (iterable of str lines), .pid,
# .poll(), .wait(), .terminate(). Matches subprocess.Popen(text=True).
Spawner = Callable[..., object]

_MAX_LINES = 5000  # cap the per-action log buffer; oldest lines drop off.
_MAX_TRACKED = 200  # cap tracked (project, action) entries; reap finished ones.


def default_spawner(cmd: list[str], cwd: Optional[str] = None) -> "subprocess.Popen[str]":
    """Spawn `cmd`, merging stderr into stdout as a line-buffered text stream."""
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
    )


class _Managed:
    def __init__(self, proc) -> None:
        self.proc = proc
        self.lines: list[str] = []
        self.offset = 0  # count of lines dropped off the front of the buffer
        self.lock = threading.Lock()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self) -> None:
        stdout = getattr(self.proc, "stdout", None)
        if stdout is None:
            return
        for line in stdout:
            with self.lock:
                self.lines.append(line.rstrip("\n"))
                if len(self.lines) > _MAX_LINES:
                    dropped = len(self.lines) - _MAX_LINES
                    del self.lines[:dropped]
                    self.offset += dropped

    def snapshot(self, since: int) -> tuple[int, list[str]]:
        with self.lock:
            total = self.offset + len(self.lines)
            start = max(0, since - self.offset)
            return total, self.lines[start:]

    def running(self) -> bool:
        return self.proc.poll() is None

    def returncode(self) -> Optional[int]:
        return self.proc.poll()

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        self.reader.join(timeout)
        return self.proc.wait(timeout=timeout)

    def stop(self) -> None:
        if self.running():
            self.proc.terminate()


class ProcessManager:
    def __init__(self, spawner: Spawner = default_spawner) -> None:
        self._spawner = spawner
        self._procs: dict[tuple[str, str], _Managed] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str, action: str, cmd: list[str],
              cwd: Optional[str] = None) -> None:
        key = (project_id, action)
        with self._lock:
            existing = self._procs.get(key)
            if existing is not None and existing.running():
                return  # already running — don't double-spawn
            self._reap_locked()
            proc = self._spawner(cmd, cwd)
            self._procs[key] = _Managed(proc)

    def _reap_locked(self) -> None:
        # Called under self._lock. Over a long session many one-shot actions
        # (build/test) accumulate; drop the oldest FINISHED entries once over the
        # cap so the dict (and per-poll status scan) can't grow without bound.
        # Reap down to below the cap so the about-to-be-added entry keeps us at
        # or under _MAX_TRACKED.
        if len(self._procs) < _MAX_TRACKED:
            return
        for k, m in list(self._procs.items()):
            if len(self._procs) < _MAX_TRACKED:
                break
            if not m.running():
                del self._procs[k]

    def is_running(self, project_id: str, action: str) -> bool:
        m = self._procs.get((project_id, action))
        return bool(m and m.running())

    def stop(self, project_id: str, action: str) -> bool:
        m = self._procs.get((project_id, action))
        if m is None:
            return False
        m.stop()
        return True

    def wait(self, project_id: str, action: str,
             timeout: Optional[float] = None) -> Optional[int]:
        m = self._procs.get((project_id, action))
        return None if m is None else m.wait(timeout)

    def logs(self, project_id: str, action: str, since: int = 0) -> tuple[int, list[str]]:
        """Return ``(next_index, lines)`` for output at/after absolute `since`."""
        m = self._procs.get((project_id, action))
        if m is None:
            return since, []
        return m.snapshot(since)

    def status(self, project_id: str) -> dict[str, dict]:
        # Snapshot under the lock — the 1s-polling status/logs endpoints must not
        # iterate the dict while start() mutates it (RuntimeError: changed size).
        with self._lock:
            items = list(self._procs.items())
        out: dict[str, dict] = {}
        for (pid, action), m in items:
            if pid != project_id:
                continue
            out[action] = {
                "running": m.running(),
                "returncode": m.returncode(),
                "pid": getattr(m.proc, "pid", None),
            }
        return out

    def stop_all(self) -> None:
        for m in list(self._procs.values()):
            m.stop()


def relio_command(subcommand: str, *args: str) -> list[str]:
    """Build a ``python -m relio <subcommand> ...`` invocation — Studio shells out
    to the installed CLI so it reuses all its logic (npm/uvicorn/docker/sdk)."""
    return [sys.executable, "-m", "relio", subcommand, *args]
