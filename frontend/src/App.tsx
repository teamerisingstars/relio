import { ChatView } from "./components/ChatView";
import { MemoryBrowser } from "./components/MemoryBrowser";

export default function App() {
  const user = "you";
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">Relio</span>
        <span className="tagline">one memory for your AI app</span>
      </header>
      <main className="layout">
        <ChatView user={user} />
        <MemoryBrowser user={user} />
      </main>
    </div>
  );
}
