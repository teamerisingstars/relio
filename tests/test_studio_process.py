# tests/test_studio_process.py
from relio.studio.process import ProcessManager


class FakeStdout:
    """An iterable of preset text lines, like Popen(text=True).stdout."""

    def __init__(self, lines):
        self._lines = list(lines)

    def __iter__(self):
        return iter(self._lines)


class FakeProc:
    def __init__(self, lines=(), pid=4321):
        self.stdout = FakeStdout(lines)
        self.pid = pid
        self._rc = None
        self.terminated = False

    def poll(self):
        return self._rc

    def wait(self, timeout=None):
        self._rc = 0
        return self._rc

    def terminate(self):
        self.terminated = True
        self._rc = -15


class FakeSpawner:
    def __init__(self, lines=()):
        self.calls = []
        self.lines = lines
        self.last = None

    def __call__(self, cmd, cwd=None):
        self.calls.append((cmd, cwd))
        self.last = FakeProc(self.lines)
        return self.last


def test_start_spawns_command_in_cwd():
    spawner = FakeSpawner()
    mgr = ProcessManager(spawner=spawner)
    mgr.start("p1", "dev", ["run", "dev"], cwd="/tmp/proj")
    assert spawner.calls == [(["run", "dev"], "/tmp/proj")]


def test_start_is_noop_when_action_already_running():
    spawner = FakeSpawner(lines=[])
    mgr = ProcessManager(spawner=spawner)
    mgr.start("p1", "dev", ["cmd"])
    mgr.start("p1", "dev", ["cmd"])  # already running -> not spawned again
    assert len(spawner.calls) == 1


def test_logs_capture_streamed_output():
    spawner = FakeSpawner(lines=["hello\n", "world\n"])
    mgr = ProcessManager(spawner=spawner)
    mgr.start("p1", "build", ["cmd"])
    mgr.wait("p1", "build")  # drain reader thread + process exit
    _, lines = mgr.logs("p1", "build")
    assert lines == ["hello", "world"]


def test_logs_since_returns_only_new_lines():
    spawner = FakeSpawner(lines=["a\n", "b\n", "c\n"])
    mgr = ProcessManager(spawner=spawner)
    mgr.start("p1", "build", ["cmd"])
    mgr.wait("p1", "build")
    nxt, first = mgr.logs("p1", "build", since=0)
    assert first == ["a", "b", "c"]
    # Nothing new past the last index.
    _, tail = mgr.logs("p1", "build", since=nxt)
    assert tail == []


def test_stop_terminates_running_process():
    spawner = FakeSpawner(lines=[])
    mgr = ProcessManager(spawner=spawner)
    mgr.start("p1", "serve", ["cmd"])
    assert mgr.stop("p1", "serve") is True
    assert spawner.last.terminated is True


def test_finished_entries_are_reaped_to_stay_bounded():
    from relio.studio.process import _MAX_TRACKED

    spawner = FakeSpawner(lines=[])
    mgr = ProcessManager(spawner=spawner)
    # Start far more one-shot actions than the cap; each FakeProc finishes.
    for i in range(_MAX_TRACKED + 60):
        mgr.start(f"p{i}", "build", ["cmd"])
        mgr.wait(f"p{i}", "build")
    assert len(mgr._procs) <= _MAX_TRACKED


def test_status_reports_running_and_finished_actions():
    spawner = FakeSpawner(lines=["x\n"])
    mgr = ProcessManager(spawner=spawner)
    mgr.start("p1", "build", ["cmd"])
    mgr.wait("p1", "build")
    status = mgr.status("p1")
    assert "build" in status
    assert status["build"]["running"] is False
    assert status["build"]["returncode"] == 0
