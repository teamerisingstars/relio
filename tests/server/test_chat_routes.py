from relio.server.llm.base import LLMProvider, Message
from relio.server.llm.fake import FakeProvider


def test_fake_provider_streams_words_and_reflects_memory_count():
    provider = FakeProvider()
    chunks = list(provider.stream([Message(role="user", content="hello there")],
                                  system="What you remember:\n- a fact\n- another"))
    text = "".join(chunks)
    assert "hello there" in text
    assert "[mem:2]" in text          # two "- " memory lines in the system prompt


def test_fake_provider_is_an_llm_provider():
    assert isinstance(FakeProvider(), LLMProvider)


from relio.memory import Memory
from relio.embedding.base import DeterministicEmbedder
from relio.record import Scope
from relio.server.agent import run_chat


def _mem(tmp_path):
    return Memory(path=str(tmp_path / "m.db"), embedder=DeterministicEmbedder(dim=16))


def test_run_chat_streams_then_captures_the_turn(tmp_path):
    m = _mem(tmp_path)
    provider = FakeProvider()
    scope = Scope(user="alice")
    chunks = list(run_chat(m, provider, "I like hiking", scope, limit=5))
    assert "I like hiking" in "".join(chunks)
    # The turn was auto-captured: a later recall finds the user message.
    found = m.recall("hiking", scope=scope, limit=5)
    assert any("hiking" in r.content for r in found)
    m.close()


def test_run_chat_injects_recalled_memory(tmp_path):
    m = _mem(tmp_path)
    m.add("Alice works at Acme", scope=Scope(user="alice"))
    provider = FakeProvider()
    chunks = list(run_chat(m, provider, "Alice works at Acme",
                           Scope(user="alice"), limit=5))
    text = "".join(chunks)
    assert "[mem:" in text and "[mem:0]" not in text   # at least one memory injected
    m.close()


import json


def _sse_payloads(raw: str):
    out = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def test_chat_streams_deltas_then_done_and_captures(client):
    resp = client.post("/api/chat", json={"message": "I enjoy chess", "user": "alice"})
    assert resp.status_code == 200
    events = _sse_payloads(resp.text)
    deltas = "".join(e["delta"] for e in events if "delta" in e)
    assert "I enjoy chess" in deltas
    assert events[-1] == {"done": True}

    # The turn was captured — searching finds the user message.
    found = client.get("/api/memory/search", params={"q": "chess", "user": "alice"})
    assert any("chess" in r["content"] for r in found.json()["results"])
