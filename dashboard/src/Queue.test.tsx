import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Queue } from "./Queue";
import { queueClaim } from "./fixtures";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function serve(claims: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(claims), {
        headers: { "content-type": "application/json" },
      }),
    ),
  );
}

it("renders a row for every claim in the queue", async () => {
  serve([
    queueClaim,
    { ...queueClaim, claim_id: "CLM-1002", customer_name: "Owen Brady" },
  ]);
  render(<Queue open={vi.fn()} />);

  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("Maya Patel")).toBeDefined();
  expect(screen.getByText("Owen Brady")).toBeDefined();
  expect(screen.getAllByText("trip delay")).toHaveLength(2);
  expect(screen.getByText("2 claims")).toBeDefined();
});

it("shows amounts in US dollars", async () => {
  serve([{ ...queueClaim, amount_claimed: 1250 }]);
  render(<Queue open={vi.fn()} />);
  expect(await screen.findByText("$1,250.00")).toBeDefined();
});

it("shows a chip for each of the four states", async () => {
  serve([
    { ...queueClaim, claim_id: "CLM-1001", status: "waiting" },
    { ...queueClaim, claim_id: "CLM-1002", status: "in_progress" },
    { ...queueClaim, claim_id: "CLM-1003", status: "awaiting_signoff" },
    { ...queueClaim, claim_id: "CLM-1004", status: "decided" },
  ]);
  render(<Queue open={vi.fn()} />);

  const rows = within(await screen.findByRole("table"));
  expect(rows.getByText("Waiting")).toBeDefined();
  expect(rows.getByText("In progress")).toBeDefined();
  expect(rows.getByText("Waiting for sign-off")).toBeDefined();
  expect(rows.getByText("Decided")).toBeDefined();
});

it("counts the claims in each state", async () => {
  serve([
    { ...queueClaim, claim_id: "CLM-1001", status: "waiting" },
    { ...queueClaim, claim_id: "CLM-1002", status: "waiting" },
    { ...queueClaim, claim_id: "CLM-1003", status: "decided" },
  ]);
  render(<Queue open={vi.fn()} />);

  const counts = await screen.findAllByText(/^\d+$/);
  expect(counts.map((node) => node.textContent)).toEqual(["2", "0", "0", "1"]);
});

it("shows the decision and payout once a claim is decided", async () => {
  serve([
    { ...queueClaim, status: "decided", decision: "approve", payout: 370 },
  ]);
  render(<Queue open={vi.fn()} />);

  expect(await screen.findByText("approve")).toBeDefined();
  expect(screen.getByText("$420.00")).toBeDefined();
  expect(screen.getByText("$370.00")).toBeDefined();
});

it("opens a claim when its row is clicked", async () => {
  serve([queueClaim]);
  const open = vi.fn();
  render(<Queue open={open} />);

  fireEvent.click(await screen.findByText("Maya Patel"));
  expect(open).toHaveBeenCalledWith("CLM-1001");
});

it("says so plainly when the queue cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Queue open={vi.fn()} />);
  expect(
    await screen.findByText(/The queue could not be loaded/),
  ).toBeDefined();
});
