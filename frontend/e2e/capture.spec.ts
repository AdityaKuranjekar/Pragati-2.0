import { expect, test } from "@playwright/test";
import fs from "node:fs";
import { fixture, IS_REAL, openApp, resetMock } from "./helpers";

test.beforeEach(async ({ page }) => resetMock(page));

test("upload CSV: mapping preview, row errors, manual override, commit, jump onward", async ({ page }) => {
  await openApp(page, "/add-data");
  // a unique extra row per run: the real server ignores a file it has already saved (same content = same job)
  const day = new Date(Date.UTC(2026, 0, 1) + (Date.now() % 31_000_000) * 60_000).toISOString().slice(0, 10);
  const buffer = Buffer.from(fs.readFileSync(fixture("attendance_messy.csv"), "utf8") + `PAT-R003,${day},P
`);
  await page.getByTestId("ingest-file").setInputFiles({ name: "attendance_messy.csv", mimeType: "text/csv", buffer });
  const table = page.getByTestId("mapping-table");
  await expect(table).toBeVisible({ timeout: 15_000 });
  const flag = table.getByLabel(/Field for column Present|कॉलम का फ़ील्ड Present/);
  // the mock guesses this column; the real server may not know the header "Present", and then you pick it by hand
  if ((await flag.inputValue()) === "") await flag.selectOption("present_flag");
  await expect(flag).toHaveValue("present_flag");
  const errors = page.getByTestId("row-errors");
  await expect(errors).toContainText("PAT26-9999");
  await expect(errors).toContainText(/maybe|not-a-date/);

  // manual override: ignoring a required column blocks saving, mapping it back allows it
  await flag.selectOption("");
  await expect(page.getByTestId("commit")).toBeDisabled();
  await expect(page.getByText(/Still needed|Map at least one of/)).toBeVisible();
  await flag.selectOption("present_flag");
  await expect(page.getByTestId("commit")).toBeEnabled();

  await page.getByTestId("commit").click();
  await expect(page.getByTestId("progress")).toBeVisible();
  await expect(page).toHaveURL(/\/weak-topics|\/support/, { timeout: 20_000 });
  await expect(page.getByText(/Saved \d+ rows from attendance_messy.csv/)).toBeVisible({ timeout: 15_000 });
});

test("OMR photo: uncertain bubbles need one-tap fixes before confirm", async ({ page }) => {
  test.skip(IS_REAL, "needs a real printed sheet image; the mock fakes the reader");
  await openApp(page, "/add-data");
  await page.getByRole("tab", { name: /OMR photo/ }).click();
  await page.getByTestId("omr-file").setInputFiles({ name: "sheet.jpg", mimeType: "image/jpeg", buffer: Buffer.alloc(60_000, 7) });
  const list = page.getByTestId("omr-uncertain");
  await expect(list).toBeVisible();
  const confirm = page.getByTestId("omr-confirm");
  await expect(confirm).toBeDisabled();
  const groups = list.getByRole("radiogroup");
  const n = await groups.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) await groups.nth(i).getByRole("radio", { name: "B" }).click();
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(page.getByText(/Sheet scored/)).toBeVisible();
  await expect(page.getByText(/OMR sheet sheet.jpg was scored and saved/)).toBeVisible({ timeout: 15_000 });
});

test("a tiny or unreadable photo asks for a retake", async ({ page }) => {
  await openApp(page, "/add-data");
  await page.getByRole("tab", { name: /OMR photo/ }).click();
  await page.getByTestId("omr-file").setInputFiles({ name: "tiny.jpg", mimeType: "image/jpeg", buffer: Buffer.alloc(2_000, 1) });
  await expect(page.getByText(/retake/i).first()).toBeVisible({ timeout: 20_000 });
});
