import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, queueClaim } from "./fixtures";

beforeEach(() => {
  window.location.hash = "";
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((path: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(path === "/api/claims" ? [queueClaim] : claim),
          {
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the queue by default", async () => {
  render(<App />);
  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(
    screen.getByRole("heading", { name: "UnderCover Claims" }),
  ).toBeDefined();
});

it("opens a claim when its row is clicked", async () => {
  render(<App />);
  fireEvent.click(await screen.findByText("Maya Patel"));
  expect(window.location.hash).toBe("#/claims/CLM-1001");
  expect(await screen.findByText(/Rome, Italy/)).toBeDefined();
});

it("shows the claim named in the hash", async () => {
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "CLM-1001" }),
  ).toBeDefined();
});
