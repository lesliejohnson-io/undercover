import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { Claim as ClaimRecord, Decision, Step } from "./api";
import { Claim } from "./Claim";
import { claim, customer, policy, steps } from "./fixtures";

const handlers = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    email: "dana.whitfield@undercover.example",
    can_approve_over_limit: true,
  },
];

const overLimit: Decision = {
  decision: "approve",
  payout: 2240,
  reason: "The tornado made the home uninhabitable.",
  policy_section: "Section 2",
  decided_at: "2026-06-30T10:00:00+00:00",
  signed_off_by: null,
  signed_off_at: null,
  paid_amount: null,
  paid_at: null,
};

const approvedOverLimit: ClaimRecord = {
  ...claim,
  status: "awaiting_signoff",
  decision: overLimit,
};

function bodyFor(path: string, record: ClaimRecord, activity: Step[]): unknown {
  if (path.endsWith("/policy")) return policy;
  if (path.endsWith("/customer")) return customer;
  if (path.endsWith("/activity")) return activity;
  if (path === "/api/handlers") return handlers;
  return record;
}

function serve(record: ClaimRecord, activity: Step[] = steps) {
  const fetchMock = vi
    .fn()
    .mockImplementation((path: string, init?: RequestInit) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            init?.method === "POST" ? record : bodyFor(path, record, activity),
          ),
          { headers: { "content-type": "application/json" } },
        ),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("shows the story, the items, the documents, the policy and the history", async () => {
  serve(claim);
  render(<Claim claimId="CLM-1001" />);

  expect(await screen.findByText(/canceled by Meridian Air/)).toBeDefined();
  expect(screen.getByText("Airport hotel, one night")).toBeDefined();
  expect(screen.getByText("Meridian Air cancellation notice")).toBeDefined();
  expect(await screen.findByText("POL-2001")).toBeDefined();
  expect(screen.getByText(/UnderCover Premium/)).toBeDefined();
  expect(
    await screen.findByText(/Checked bag arrived 30 hours late/),
  ).toBeDefined();
  expect(
    screen.getByText("The agent has not decided this claim yet."),
  ).toBeDefined();
});

it("shows the decision with its reason and policy section", async () => {
  serve({
    ...claim,
    status: "decided",
    decision: {
      decision: "approve",
      payout: 420,
      reason: "A six hour delay on a Premium plan.",
      policy_section: "Section 3",
      decided_at: "2026-06-25T09:00:00+00:00",
      signed_off_by: null,
      signed_off_at: null,
      paid_amount: 420,
      paid_at: "2026-06-25T09:01:00+00:00",
    },
  });
  render(<Claim claimId="CLM-1001" />);

  expect(await screen.findByText("approve")).toBeDefined();
  expect(screen.getByText("A six hour delay on a Premium plan.")).toBeDefined();
  expect(screen.getByText("Section 3")).toBeDefined();
  expect(screen.getByText("Paid $420.00.")).toBeDefined();
  expect(screen.queryByRole("button", { name: /Pay/ })).toBeNull();
});

it("polls the activity while the claim is in progress and stops after", async () => {
  const growing = [...steps];
  serve({ ...claim, status: "in_progress" }, growing);
  render(<Claim claimId="CLM-1001" />);

  expect(await screen.findByText("Started")).toBeDefined();
  growing.push({
    step: "Read the claim",
    detail: "Flight home canceled",
    at: "2026-06-25T09:00:01+00:00",
  });
  vi.advanceTimersByTime(1000);
  expect(await screen.findByText("Read the claim")).toBeDefined();

  cleanup();
  const settledMock = serve({ ...claim, status: "decided" }, growing);
  render(<Claim claimId="CLM-1001" />);
  await screen.findByText("Read the claim");
  const calls = settledMock.mock.calls.length;
  vi.advanceTimersByTime(5000);
  expect(settledMock.mock.calls).toHaveLength(calls);
});

it("keeps polling an approval that the agent has not paid yet", async () => {
  const unpaid: ClaimRecord = {
    ...claim,
    status: "decided",
    decision: { ...overLimit, payout: 420 },
  };
  const fetchMock = serve(unpaid);
  render(<Claim claimId="CLM-1001" />);

  await screen.findByText("Not paid.");
  const calls = fetchMock.mock.calls.length;
  vi.advanceTimersByTime(2000);
  await waitFor(() => {
    expect(fetchMock.mock.calls.length).toBeGreaterThan(calls);
  });
});

it("offers sign-off, and only then payment, for a claim over the limit", async () => {
  const fetchMock = serve(approvedOverLimit);
  render(<Claim claimId="CLM-1001" />);

  expect(await screen.findByText(/is over the approval limit/)).toBeDefined();
  expect(screen.queryByRole("button", { name: /Pay/ })).toBeNull();
  expect(
    screen.getByRole("button", { name: "Sign off" }).hasAttribute("disabled"),
  ).toBe(true);

  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign off" }));

  await waitFor(() => {
    expect(
      fetchMock.mock.calls.some(
        (call) => call[0] === "/api/claims/CLM-1001/signoff",
      ),
    ).toBe(true);
  });
});

it("pays a signed off claim", async () => {
  const fetchMock = serve({
    ...approvedOverLimit,
    decision: {
      ...overLimit,
      signed_off_by: "HND-01",
      signed_off_at: "2026-06-30T11:00:00+00:00",
    },
  });
  render(<Claim claimId="CLM-1001" />);

  fireEvent.click(await screen.findByRole("button", { name: "Pay $2,240.00" }));
  await waitFor(() => {
    expect(
      fetchMock.mock.calls.some(
        (call) => call[0] === "/api/claims/CLM-1001/payment",
      ),
    ).toBe(true);
  });
});

it("runs the agent", async () => {
  const fetchMock = serve(claim);
  render(<Claim claimId="CLM-1001" />);

  fireEvent.click(await screen.findByRole("button", { name: "Run the agent" }));
  await waitFor(() => {
    expect(
      fetchMock.mock.calls.some(
        (call) => call[0] === "/api/claims/CLM-1001/run",
      ),
    ).toBe(true);
  });
});

it("shows what the backend refused", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((path: string, init?: RequestInit) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            init?.method === "POST"
              ? { detail: "CLM-1001 is paid" }
              : bodyFor(path, claim, steps),
          ),
          {
            status: init?.method === "POST" ? 409 : 200,
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    ),
  );
  render(<Claim claimId="CLM-1001" />);

  fireEvent.click(await screen.findByRole("button", { name: "Run the agent" }));
  expect(await screen.findByText("CLM-1001 is paid")).toBeDefined();
});

it("drops a refusal when another claim is opened", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((path: string, init?: RequestInit) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            init?.method === "POST"
              ? { detail: "CLM-1001 is paid" }
              : bodyFor(path, claim, steps),
          ),
          {
            status: init?.method === "POST" ? 409 : 200,
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    ),
  );
  const { rerender } = render(<Claim claimId="CLM-1001" />);

  fireEvent.click(await screen.findByRole("button", { name: "Run the agent" }));
  await screen.findByText("CLM-1001 is paid");

  rerender(<Claim claimId="CLM-1008" />);
  await waitFor(() => {
    expect(screen.queryByText("CLM-1001 is paid")).toBeNull();
  });
});

it("says so plainly when the claim cannot be loaded", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<Claim claimId="CLM-1001" />);
  expect(await screen.findByText(/could not be loaded/)).toBeDefined();
});
