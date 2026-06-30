// tests/MemoryBrowser.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { MemoryBrowser } from "../src/components/MemoryBrowser";
import { searchMemory, addMemory, deleteMemory } from "../src/api/client";

vi.mock("../src/api/client", () => ({
  searchMemory: vi.fn(),
  addMemory: vi.fn(),
  deleteMemory: vi.fn(),
}));

const rec = (id: string, content: string) =>
  ({ id, content, type: "semantic" }) as never;

test("searching renders result rows", async () => {
  (searchMemory as ReturnType<typeof vi.fn>).mockResolvedValue({
    results: [rec("mem_1", "apple pie recipe")],
    text: "- apple pie recipe",
  });
  const user = userEvent.setup();
  render(<MemoryBrowser user="you" />);
  await user.type(screen.getByLabelText("search"), "apple");
  await user.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByText("apple pie recipe")).toBeInTheDocument();
});

test("adding a memory calls addMemory then refreshes", async () => {
  (addMemory as ReturnType<typeof vi.fn>).mockResolvedValue(rec("mem_2", "new note"));
  (searchMemory as ReturnType<typeof vi.fn>).mockResolvedValue({ results: [], text: "" });
  const user = userEvent.setup();
  render(<MemoryBrowser user="you" />);
  await user.type(screen.getByLabelText("new memory"), "new note");
  await user.click(screen.getByRole("button", { name: "Add" }));
  expect(addMemory).toHaveBeenCalledWith("new note", { user: "you" });
});

test("deleting a result removes its row", async () => {
  (searchMemory as ReturnType<typeof vi.fn>).mockResolvedValue({
    results: [rec("mem_1", "apple pie recipe")],
    text: "",
  });
  (deleteMemory as ReturnType<typeof vi.fn>).mockResolvedValue({ deleted: true });
  const user = userEvent.setup();
  render(<MemoryBrowser user="you" />);
  await user.type(screen.getByLabelText("search"), "apple");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByText("apple pie recipe");
  await user.click(screen.getByLabelText("delete mem_1"));
  expect(deleteMemory).toHaveBeenCalledWith("mem_1");
  await waitFor(() =>
    expect(screen.queryByText("apple pie recipe")).not.toBeInTheDocument(),
  );
});

test("shows an error when search fails", async () => {
  (searchMemory as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("nope"));
  const user = userEvent.setup();
  render(<MemoryBrowser user="you" />);
  await user.type(screen.getByLabelText("search"), "x");
  await user.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("nope");
});
