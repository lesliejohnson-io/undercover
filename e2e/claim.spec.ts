import { expect, test, type Page } from "@playwright/test";
import { BACKEND } from "./where";

async function decide(
  page: Page,
  claimId: string,
  payout: number,
): Promise<void> {
  await page.request.post(`${BACKEND}/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout,
      reason:
        "The tornado made the home uninhabitable and the costs are receipted.",
      policy_section: "Section 2",
    },
  });
}

test("a claim shows its story, documents, policy and history", async ({
  page,
}) => {
  await page.goto("/#/claims/CLM-1001");

  await expect(page.getByRole("heading", { name: "CLM-1001" })).toBeVisible();
  await expect(page.getByText(/canceled by Meridian Air/)).toBeVisible();
  await expect(page.getByText("Airport hotel, one night")).toBeVisible();
  await expect(
    page.getByText("Meridian Air cancellation notice"),
  ).toBeVisible();
  await expect(page.getByText("POL-2001")).toBeVisible();
  await expect(page.getByText(/UnderCover Premium/)).toBeVisible();
  await expect(
    page.getByText(/Checked bag arrived 30 hours late/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run the agent" }),
  ).toBeVisible();
});

test("a payout over the limit waits for a sign-off before it can be paid", async ({
  page,
}) => {
  await decide(page, "CLM-1008", 2240);
  await page.goto("/#/claims/CLM-1008");

  await expect(page.getByText("Waiting for sign-off")).toBeVisible();
  await expect(page.getByText(/is over the approval limit/)).toBeVisible();
  await expect(page.getByRole("button", { name: /^Pay/ })).toBeHidden();

  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off" }).click();

  const pay = page.getByRole("button", { name: "Pay $2,240.00" });
  await expect(pay).toBeVisible();
  await pay.click();

  await expect(page.getByText("Decided")).toBeVisible();
  await expect(page.getByText("Paid $2,240.00.")).toBeVisible();
});

test("the agent's instructions are shown read only", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();

  await expect(
    page.getByRole("heading", { name: "The agent's instructions" }),
  ).toBeVisible();
  await expect(page.getByText("You are the UnderCover Agent")).toBeVisible();
  await expect(page.getByText("Refer rather than guess")).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);

  const served = await page.request.get(`${BACKEND}/api/instructions`);
  expect(await page.locator("pre.instructions").innerText()).toContain(
    "Working out the payout",
  );
  expect(await served.text()).toContain("Working out the payout");
});
