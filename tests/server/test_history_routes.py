import json
from typing import Iterator

from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import Scope
from relio.server.agent import run_chat
from relio.server.llm.base import LLMProvider, Message
from relio.server.llm.fake import FakeProvider


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))


class RecordingProvider(LLMProvider):
    """Captures the message list it was handed, so replay can be asserted."""

    def __init__(self) -> None:
        self.seen: list[Message] = []

    def stream(self, messages: list[Message], system: str) -> Iterator[str]:
        self.seen = list(messages)
        yield "ok"


def test_run_chat_replays_prior_history(tmp_path):
    m = _mem(tmp_path)
    scope = Scope(user="alice", session="s1")
    list(run_chat(m, FakeProvider(), "first message", scope))
    rec = RecordingProvider()
    list(run_chat(m, rec, "second message", scope))
    seen = [(msg.role, msg.content) for msg in rec.seen]
    assert ("user", "first message") in seen
    assert any(role == "assistant" for role, _ in seen)
    assert seen[-1] == ("user", "second message")
    m.close()


def test_run_chat_persists_both_turns(tmp_path):
    m = _mem(tmp_path)
    scope = Scope(user="alice", session="s1")
    list(run_chat(m, FakeProvider(reply="hi there"), "hello", scope))
    hist = m.history(scope)
    assert [(h.metadata["role"], h.content.strip()) for h in hist] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]
    m.close()


def test_history_endpoint_returns_session_transcript(client):
    client.post("/api/chat", json={"message": "hello", "user": "alice", "session": "s1"})
    client.post("/api/chat", json={"message": "again", "user": "alice", "session": "s1"})
    resp = client.get("/api/history", params={"user": "alice", "session": "s1"})
    assert resp.status_code == 200
    turns = resp.json()["turns"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
    assert turns[0]["content"] == "hello"
    assert turns[2]["content"] == "again"


def test_history_endpoint_is_scope_isolated(client):
    client.post("/api/chat", json={"message": "alice msg", "user": "alice", "session": "s1"})
    client.post("/api/chat", json={"message": "bob msg", "user": "bob", "session": "s2"})
    resp = client.get("/api/history", params={"user": "alice", "session": "s1"})
    turns = resp.json()["turns"]
    assert all(t["content"] != "bob msg" for t in turns)
    assert turns[0]["content"] == "alice msg"
