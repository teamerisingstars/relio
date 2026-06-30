import { RelioClient } from "./sdk/client";
import { ChatView } from "./components/ChatView";
import { MemoryBrowser } from "./components/MemoryBrowser";

// Same-origin in production (backend serves these assets); Vite proxies /api in dev.
const client = new RelioClient("");

export function App() {
  return (
    <main className="app">
      <header className="app-header">
        <h1>Relio</h1>
      </header>
      <div className="panes">
        <ChatView client={client} />
        <MemoryBrowser client={client} />
      </div>
    </main>
  );
}
