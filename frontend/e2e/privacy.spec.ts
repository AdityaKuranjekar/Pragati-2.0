import { expect, test } from "@playwright/test";
import { IS_REAL, openApp, resetMock } from "./helpers";

test.beforeEach(async ({ page }) => resetMock(page));

test("switch to academic-only: the honest accuracy cost is shown, then the list size changes", async ({ page }) => {
  await openApp(page, "/privacy");
  await expect(page.getByTestId("tier-table")).toBeVisible({ timeout: 15_000 });
  await page.getByText(/Academic only/).first().click();
  await expect(page.getByTestId("tier-cost")).toContainText("honest cost");
  await page.getByTestId("apply-tier").click();
  await expect(page.getByTestId("tier-result")).toContainText(/went from \d+ to \d+/, { timeout: 20_000 });
  // put it back so later specs see the default
  await page.getByText(/^Full/).first().click();
  await page.getByTestId("apply-tier").click();
  await expect(page.getByTestId("tier-result")).toContainText(/went from/, { timeout: 20_000 });
});

test("withdraw a consent: row shows processing halted", async ({ page }) => {
  test.skip(IS_REAL, "withdrawing a consent changes the real database for later runs");
  await openApp(page, "/privacy");
  const table = page.getByTestId("consent-table");
  await expect(table).toBeVisible({ timeout: 15_000 });
  await table.getByTestId("withdraw").first().click();
  await page.getByTestId("confirm-withdraw").click();
  await expect(page.getByTestId("consent-msg")).toContainText(/halted|stopped/i);
});

test("consent ledger lists guardians", async ({ page }) => {
  await openApp(page, "/privacy");
  await expect(page.getByTestId("consent-table")).toBeVisible({ timeout: 15_000 });
});
