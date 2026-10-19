import { expect, it } from "vitest";
import { routeOf } from "./route";

it("reads the queue, a claim and the instructions out of the hash", () => {
  expect(routeOf("")).toEqual({ page: "queue" });
  expect(routeOf("#/")).toEqual({ page: "queue" });
  expect(routeOf("#/claims/CLM-1001")).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
  expect(routeOf("#/instructions")).toEqual({ page: "instructions" });
  expect(routeOf("#/nonsense")).toEqual({ page: "queue" });
});
