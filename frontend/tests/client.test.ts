// tests/client.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { addMemory, searchMemory, deleteMemory } from "../src/api/client";

afterEach(() => vi.restoreAllMocks());

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("memory client", () => {
  it("addMemory posts content + user and returns the record", async () => {
    const rec = { id: "mem_1", content: "hi", type: "semantic" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(rec));
    const out = await addMemory("hi", { user: "you" });
    expect(out).toEqual(rec);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/memory");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ content: "hi", user: "you" });
  });

  it("searchMemory builds the query string and returns results", async () => {
    const body = { results: [{ id: "mem_1", content: "hi", type: "semantic" }], text: "- hi" };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(body));
    const out = await searchMemory("hi", { user: "you", limit: 3 });
    expect(out.results).toHaveLength(1);
    expect(out.text).toBe("- hi");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/memory/search?q=hi&user=you&limit=3");
  });

  it("deleteMemory DELETEs by id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ deleted: true }));
    const out = await deleteMemory("mem_1");
    expect(out).toEqual({ deleted: true });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/memory/mem_1");
    expect(fetchMock.mock.calls[0][1]?.method).toBe("DELETE");
  });
});

import { chatStream } from "../src/api/client";

function sseResponse(frames: string[]) {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(enc.encode(f));
      controller.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("chatStream", () => {
  it("yields deltas and stops at done", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse([
        'data: {"delta": "Hel"}\n\n',
        'data: {"delta": "lo"}\n\n',
        'data: {"done": true}\n\n',
      ]),
    );
    const out: string[] = [];
    for await (const d of chatStream("hi", { user: "you" })) out.push(d);
    expect(out.join("")).toBe("Hello");
  });

  it("throws on an error frame", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse(['data: {"error": "boom"}\n\n']),
    );
    await expect(async () => {
      for await (const _ of chatStream("hi")) void _;
    }).rejects.toThrow("boom");
  });
});
