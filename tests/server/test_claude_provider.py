from relio.server.llm.base import Message


class _FakeStream:
    def __init__(self, texts):
        self.text_stream = iter(texts)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeMessages:
    def __init__(self, texts):
        self._texts = texts
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self._texts)


class _FakeClient:
    def __init__(self, texts):
        self.messages = _FakeMessages(texts)


def test_claude_provider_yields_text_and_drops_system_role():
    from relio.server.llm.claude import ClaudeProvider

    fake = _FakeClient(["Hel", "lo"])
    provider = ClaudeProvider(model="claude-opus-4-8", client=fake)
    out = list(provider.stream(
        [Message(role="system", content="ignored"), Message(role="user", content="hi")],
        system="remember: x",
    ))
    assert out == ["Hel", "lo"]
    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-opus-4-8"
    assert sent["system"] == "remember: x"
    # system-role messages are passed via `system=`, not in the messages list
    assert sent["messages"] == [{"role": "user", "content": "hi"}]
