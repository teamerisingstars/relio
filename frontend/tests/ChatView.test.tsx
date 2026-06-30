// tests/ChatView.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ChatView } from "../src/components/ChatView";
import { chatStream } from "../src/api/client";

vi.mock("../src/api/client", () => ({
  chatStream: vi.fn(async function* () {
    yield "Hi ";
    yield "there";
  }),
}));

test("sends a message and renders the streamed reply", async () => {
  const user = userEvent.setup();
  render(<ChatView user="you" />);
  await user.type(screen.getByLabelText("message"), "hello");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("hello")).toBeInTheDocument();        // user bubble
  expect(await screen.findByText("Hi there")).toBeInTheDocument();     // streamed assistant bubble
});

test("renders an error bubble when the stream fails", async () => {
  (chatStream as ReturnType<typeof vi.fn>).mockImplementation(async function* () {
    throw new Error("boom");
  });
  const user = userEvent.setup();
  render(<ChatView user="you" />);
  await user.type(screen.getByLabelText("message"), "hello");
  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText(/⚠️ boom/)).toBeInTheDocument();
});
