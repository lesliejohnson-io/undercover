import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Instructions } from "./Instructions";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions and offers no way to edit them", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("# The UnderCover Agent\n\nRefer rather than guess."),
      ),
  );
  render(<Instructions />);

  expect(await screen.findByText(/Refer rather than guess/)).toBeDefined();
  expect(
    screen.getByText("Read only. This is the text the agent runs on."),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("says so plainly when the instructions cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Instructions />);
  expect(await screen.findByText(/could not be loaded/)).toBeDefined();
});
