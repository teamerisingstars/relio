// src/components/ChatView.tsx
import { useState } from "react";
import { chatStream } from "../api/client";

interface Msg {
  role: "user" | "assistant";
  text: string;
}

export function ChatView({ user }: { user: string }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    try {
      for await (const delta of chatStream(text, { user })) {
        setMessages((m) => {
          const copy = m.slice();
          const last = copy[copy.length - 1];
          copy[copy.length - 1] = { role: "assistant", text: last.text + delta };
          return copy;
        });
      }
    } catch (err) {
      setMessages((m) => {
        const copy = m.slice();
        copy[copy.length - 1] = { role: "assistant", text: `⚠️ ${(err as Error).message}` };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="chat">
      <ul className="messages" aria-label="messages">
        {messages.map((m, i) => (
          <li key={i} className={`bubble ${m.role}`}>
            {m.text}
          </li>
        ))}
      </ul>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          aria-label="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask Relio…"
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          Send
        </button>
      </form>
    </section>
  );
}
