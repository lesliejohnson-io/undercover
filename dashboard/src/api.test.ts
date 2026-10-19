import { afterEach, expect, it, vi, type Mock } from "vitest";
import { api, claimTypeLabel, money, stateLabels } from "./api";

type Call = [string, RequestInit | undefined];

afterEach(() => {
  vi.unstubAllGlobals();
});

function calls(fetchMock: Mock): Call[] {
  return fetchMock.mock.calls as Call[];
}

function urls(fetchMock: Mock): string[] {
  return calls(fetchMock).map(([url]) => url);
}

function serve(body: unknown, ok = true) {
  const fetchMock = vi.fn().mockImplementation(() =>
    Promise.resolve(
      new Response(typeof body === "string" ? body : JSON.stringify(body), {
        status: ok ? 200 : 409,
        headers: { "content-type": "application/json" },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

it("reads each record from its own route", async () => {
  const fetchMock = serve([]);
  await api.queue();
  await api.claim("CLM-1001");
  await api.policy("CLM-1001");
  await api.customer("CLM-1001");
  await api.activity("CLM-1001");
  await api.handlers();

  expect(urls(fetchMock)).toEqual([
    "/api/claims",
    "/api/claims/CLM-1001",
    "/api/claims/CLM-1001/policy",
    "/api/claims/CLM-1001/customer",
    "/api/claims/CLM-1001/activity",
    "/api/handlers",
  ]);
});

it("reads the instructions as text", async () => {
  serve("# The UnderCover Agent");
  expect(await api.instructions()).toBe("# The UnderCover Agent");
});

it("posts a run, a sign-off and a payment", async () => {
  const fetchMock = serve({});
  await api.run("CLM-1001");
  await api.signOff("CLM-1001", "HND-01");
  await api.pay("CLM-1001", 420);

  expect(urls(fetchMock)).toEqual([
    "/api/claims/CLM-1001/run",
    "/api/claims/CLM-1001/signoff",
    "/api/claims/CLM-1001/payment",
  ]);
  expect(calls(fetchMock).map(([, init]) => init?.body)).toEqual([
    "{}",
    '{"handler_id":"HND-01"}',
    '{"amount":420}',
  ]);
});

it("raises what the backend refused", async () => {
  serve({ detail: "needs a handler's sign-off" }, false);
  await expect(api.pay("CLM-1001", 2400)).rejects.toThrow(
    "needs a handler's sign-off",
  );
});

it("raises when a read fails", async () => {
  serve({ detail: "No claim CLM-9999" }, false);
  await expect(api.claim("CLM-9999")).rejects.toThrow("returned 409");
  serve("nope", false);
  await expect(api.instructions()).rejects.toThrow("returned 409");
});

it("formats money, states and claim types for the handlers", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
  expect(stateLabels.awaiting_signoff).toBe("Waiting for sign-off");
  expect(claimTypeLabel("baggage_delay")).toBe("baggage delay");
});
