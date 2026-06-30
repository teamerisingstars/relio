// tests/smoke.test.tsx  (replace contents)
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";
import App from "../src/App";

vi.mock("../src/api/client", () => ({
  chatStream: vi.fn(async function* () {}),
  searchMemory: vi.fn().mockResolvedValue({ results: [], text: "" }),
  addMemory: vi.fn(),
  deleteMemory: vi.fn(),
}));

test("App renders brand, chat composer, and memory browser", () => {
  render(<App />);
  expect(screen.getByText("Relio")).toBeInTheDocument();
  expect(screen.getByLabelText("message")).toBeInTheDocument();
  expect(screen.getByLabelText("search")).toBeInTheDocument();
});
