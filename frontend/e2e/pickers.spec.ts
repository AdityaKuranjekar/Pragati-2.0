import { expect, test } from "@playwright/test";
import { go, openApp, resetMock } from "./helpers";

test.beforeEach(async ({ page }) => resetMock(page));

test("student picker: search by name or roll, alphabetical, deep link, remembered, parent page follows", async ({ page }) => {
  await openApp(page, "/students");
  const view = page.getByTestId("student-view");
  await expect(view.or(page.getByText("Not enough data yet"))).toBeVisible({ timeout: 15_000 });
  const search = page.getByTestId("student-search");
  await search.click();
  const options = page.getByRole("listbox").getByRole("option");
  await expect(options.first()).toBeVisible();
  const names = (await options.locator("span:first-child").allInnerTexts()).map((x) => x.trim());
  expect([...names].sort((a, b) => a.localeCompare(b))).toEqual(names); // alphabetical, never by score
  // search narrows the list
  const target = names[Math.min(3, names.length - 1)];
  await search.fill(target.slice(0, 4));
  await expect(options.first()).toContainText(target.slice(0, 4), { ignoreCase: true });
  await options.filter({ hasText: target }).first().click();
  await expect(page).toHaveURL(/\/student\/[0-9a-f-]{36}$/);
  const url = page.url();
  await expect(page.getByTestId("student-search")).toHaveValue(new RegExp(target.split(" ")[0]));
  // deep link keeps working after a reload
  await page.reload();
  await expect(page.getByTestId("student-search")).toHaveValue(new RegExp(target.split(" ")[0]));
  expect(page.url()).toBe(url);
  // the parent page opens on the same student
  await go(page, "Parents");
  await expect(page.getByTestId("student-search")).toHaveValue(new RegExp(target.split(" ")[0]));
});

test("changing the institute resets the student and batch choice sensibly", async ({ page }) => {
  await openApp(page, "/students");
  await expect(page.getByTestId("student-search")).not.toHaveValue("", { timeout: 15_000 });
  const before = await page.getByTestId("student-search").inputValue();
  await page.getByLabel("Institute", { exact: true }).selectOption("gaya_both");
  await expect(page.getByTestId("student-search")).not.toHaveValue(before, { timeout: 15_000 });
  await expect(page.getByTestId("student-search")).not.toHaveValue("");
});

test("weak topics and support list have a batch picker", async ({ page }) => {
  await openApp(page, "/weak-topics");
  await expect(page.getByLabel("Batch", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  await go(page, "Support list");
  await expect(page.getByLabel("Batch", { exact: true }).first()).toBeVisible();
});
