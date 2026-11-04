import { expect, test } from "@playwright/test";
import { openApp, resetMock } from "./helpers";

test.beforeEach(async ({ page }) => resetMock(page));

test("parent view: WhatsApp preview, then a Hindi report with checks", async ({ page }) => {
  await openApp(page, "/parents");
  await expect(page.getByTestId("parent-view")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("WhatsApp messages")).toBeVisible();
  await page.getByRole("radio", { name: "हिन्दी" }).click();
  await page.getByTestId("make-report").click();
  await expect(page.getByTestId("report-result")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("verified-badge")).toContainText(/checks passed|Held back/);
  await expect(page.getByTestId("source-badge")).toBeVisible();
});

test("asking for the local model while it is down falls back to the template and says so", async ({ page }) => {
  await openApp(page, "/students");
  await expect(page.getByTestId("student-view")).toBeVisible({ timeout: 20_000 });
  await page.getByText("Try the local language model first").click();
  await page.getByTestId("make-report").click();
  await expect(page.getByTestId("report-result")).toBeVisible({ timeout: 25_000 });
  await expect(page.getByTestId("source-badge")).toContainText(/template|local model/);
});

test("student page shows only that student: no peers, no batch data", async ({ page }) => {
  await openApp(page, "/students");
  await expect(page.getByTestId("student-view")).toBeVisible({ timeout: 20_000 });
  const text = await page.getByTestId("student-view").innerText();
  expect(text).not.toMatch(/rank #|leaderboard|compared with others|batch average|top performer/i);
});
