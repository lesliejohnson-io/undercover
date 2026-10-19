import { expect, test } from "@playwright/test";

test("the queue lists the claims with where each one stands", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "UnderCover Claims" }),
  ).toBeVisible();

  const row = page.getByRole("row").filter({ hasText: "CLM-1001" });
  await expect(row).toContainText("Maya Patel");
  await expect(row).toContainText("trip delay");
  await expect(row).toContainText("$420.00");

  await expect(page.getByRole("row")).toHaveCount(26);
});

test("a row opens the claim", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("row").filter({ hasText: "CLM-1001" }).click();

  await expect(page).toHaveURL(/#\/claims\/CLM-1001$/);
  await expect(page.getByRole("heading", { name: "CLM-1001" })).toBeVisible();
  await expect(page.getByText("Rome, Italy")).toBeVisible();
});
