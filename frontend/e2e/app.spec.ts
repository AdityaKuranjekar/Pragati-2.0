import { expect, test } from "@playwright/test";
import { go, openApp, resetMock } from "./helpers";

test.beforeEach(async ({ page }) => resetMock(page));

test("the app opens straight into the product: no login, one navigation, small top bar", async ({ page }) => {
  await openApp(page);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText(/sign in|log in/i)).toHaveCount(0);
  await expect(page.locator("nav")).toHaveCount(1); // exactly one navigation in the whole page (the sidebar; a drawer on phones)
  await expect(page.getByTestId("page-title")).toHaveText("Home");
  await expect(page.getByTestId("headline-numbers")).toBeVisible();
  await expect(page.getByTestId("primary-cta")).toContainText("Next step: Add data");
});

// Every page, one after the other, with NO reload in between: content must be visible each time.
const PAGES: [string | RegExp, string, RegExp][] = [
  ["Add data", "Add data", /Spreadsheet|CSV/],
  ["Weak topics", "Weak topics", /Topic by topic/],
  ["Support list", "Support list", /This week/],
  ["Students", "Students", /Hi |नमस्ते|Not enough data/],
  ["Parents", "Parents", /Monthly report|Not enough data/],
  ["Results", "Results", /Retention by month/],
  ["Privacy and consent", "Privacy and consent", /What the early-warning model may use/],
  ["How it works and evidence", "How it works and evidence", /./],
  ["Home", "Home", /This week's checklist/],
];
test("click through every page in sequence without reloading", async ({ page }) => {
  await openApp(page);
  await page.evaluate(() => ((window as unknown as { __marker: number }).__marker = 1));
  for (let round = 0; round < 2; round++) {
    for (const [link, title, text] of PAGES) {
      await go(page, link);
      await expect(page.getByTestId("page-title")).toHaveText(title === "How it works and evidence" ? /How it works/ : title);
      await expect(page.getByRole("main")).toContainText(text, { timeout: 15_000 });
      await expect(page.getByRole("main").locator('[aria-busy="true"]')).toHaveCount(0, { timeout: 15_000 });
    }
  }
  // still the same document: nothing reloaded the page
  expect(await page.evaluate(() => (window as unknown as { __marker?: number }).__marker)).toBe(1);
});

test("the three About tabs each show content", async ({ page }) => {
  await openApp(page, "/about");
  for (const [tab, text] of [["Data card", /./], ["Evidence", /Model vs your current rule/], ["How it works", /./]] as const) {
    await page.getByRole("navigation", { name: "Evidence sections" }).getByRole("link", { name: tab }).click();
    await expect(page.getByRole("main")).toContainText(text, { timeout: 15_000 });
  }
});

test("working screens show no model jargon", async ({ page }) => {
  await openApp(page);
  for (const link of ["Weak topics", "Support list", "Students", "Parents"]) {
    await go(page, link);
    await expect(page.getByRole("main")).toContainText(/./);
    await page.waitForTimeout(500);
    const text = await page.getByRole("main").innerText();
    expect(text, link).not.toMatch(/\b(theta|AUC|LightGBM|SHAP|logit|synthetic|leaderboard)\b/i);
  }
});

test("a 401 gets a silent new demo token, no redirect", async ({ page }) => {
  await openApp(page);
  await page.evaluate(() => {
    const s = JSON.parse(localStorage.getItem("pragati.session.v2") || "{}");
    s.token = "stale";
    localStorage.setItem("pragati.session.v2", JSON.stringify(s));
  });
  await page.reload();
  await expect(page.getByTestId("headline-numbers")).toBeVisible({ timeout: 15_000 });
  await expect(page).toHaveURL(/\/$/);
});
