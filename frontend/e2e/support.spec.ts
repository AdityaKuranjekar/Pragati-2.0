import { expect, test } from "@playwright/test";
import { go, IS_REAL, openApp, openSupportWithRows, resetMock } from "./helpers";

test.beforeEach(async ({ page }) => resetMock(page));

test("support list: names, reasons, a kind next step, never ranked", async ({ page }) => {
  const list = await openSupportWithRows(page);
  await expect(list.locator("li").first()).toBeVisible({ timeout: 15_000 });
  const text = await page.getByRole("main").innerText();
  expect(text).not.toMatch(/rank #|leaderboard|top performer|priority \d/i);
  await expect(list.locator("li").first()).toContainText("→");
});

test("edit attendance: server validation message, then the list updates in place", async ({ page }) => {
  const list = await openSupportWithRows(page);
  await expect(list.locator("li").first()).toBeVisible({ timeout: 15_000 });
  const row = list.locator("li").first();
  await row.getByTestId("row-details").click();
  await row.getByTestId("edit-attendance").click();
  await row.getByTestId("attendance-input").fill("140");
  await row.getByTestId("attendance-save").click();
  await expect(row.getByTestId("attendance-error")).toContainText(/100/);
  await row.getByTestId("attendance-input").fill("95");
  await row.getByTestId("attendance-save").click();
  await expect(page.getByTestId("edit-note")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("refresh-list").click();
  await expect(page.getByTestId("support-list").or(page.getByTestId("empty-state"))).toBeVisible();
});

test("try-a-change panel validates for any student in the batch", async ({ page }) => {
  await openApp(page, "/support");
  const input = page.getByTestId("attendance-input").last();
  await expect(input).toBeVisible({ timeout: 15_000 });
  await input.fill("150");
  await page.getByTestId("attendance-save").last().click();
  await expect(page.getByTestId("attendance-error").last()).toContainText(/100/);
});

test("flagged question: fix the key and see it marked fixed", async ({ page }) => {
  test.skip(IS_REAL, "the real server only flags keys when the data shows a problem");
  await openApp(page, "/weak-topics");
  const fix = page.getByTestId("fix-key-17");
  await expect(fix).toBeVisible({ timeout: 15_000 });
  await fix.click();
  await expect(page.getByText(/students re-scored/)).toBeVisible();
  await expect(page.getByTestId("flagged-list").getByText("Key fixed")).toHaveCount(1);
});

test("weak topics shows the topic map and the answer-key check", async ({ page }) => {
  await openApp(page, "/weak-topics");
  await expect(page.getByTestId("heatmap-card")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Answer-key check")).toBeVisible();
  await go(page, "Home");
  await expect(page.getByTestId("page-title")).toHaveText("Home");
});
