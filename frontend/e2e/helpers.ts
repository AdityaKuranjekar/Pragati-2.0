import { expect, type Page } from "@playwright/test";
import path from "node:path";

export const IS_REAL = !!process.env.E2E_REAL;

/** Open the app straight into the product (no login). English is pinned unless a spec sets another language. */
export async function openApp(page: Page, to = "/", lang = "en") {
  await page.addInitScript((l) => localStorage.setItem("pragati.lang", localStorage.getItem("pragati.lang") ?? l), lang);
  await page.goto(to);
  await expect(page.getByTestId("page-title")).toBeVisible();
}

/** Click a link in the one navigation (sidebar, or the menu drawer on phones). */
export async function go(page: Page, name: string | RegExp) {
  const menu = page.getByTestId("menu-button");
  if (await menu.isVisible()) {
    await menu.click();
    await page.getByRole("dialog").getByRole("link", { name }).click();
  } else {
    await page.getByTestId("sidebar").getByRole("link", { name }).click();
  }
}

export const fixture = (name: string) => path.join(__dirname, "fixtures", name);

/** Mock-only: forget edits so every spec starts from the seeded state. */
export async function resetMock(page: Page) {
  if (!IS_REAL) await page.request.post("/api/mock/dev/reset");
}

/** Open the support list on a batch that has people on it (the mock's batches are not all non-empty). */
export async function openSupportWithRows(page: Page) {
  await openApp(page, "/support");
  const list = page.getByTestId("support-list");
  const empty = page.getByTestId("empty-state");
  await expect(list.or(empty)).toBeVisible({ timeout: 20_000 });
  const select = page.getByLabel("Batch", { exact: true }).first();
  const values = await select.locator("option").evaluateAll((os) => os.map((o) => (o as HTMLOptionElement).value));
  for (const v of values) {
    if (await list.isVisible()) return list;
    await select.selectOption(v);
    await expect(list.or(empty)).toBeVisible({ timeout: 20_000 });
  }
  await expect(list).toBeVisible();
  return list;
}
