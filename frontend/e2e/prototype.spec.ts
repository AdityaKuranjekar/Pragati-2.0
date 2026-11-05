import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const SHOTS = path.join(__dirname, "..", "..", "docs", "pragati-2.0", "orchestration", "s4_screenshots");
const shot = (page: Page, name: string) => page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
const R_CELL = "cell-demo-a-roots_nature";

const noHorizontalScroll = async (page: Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

test.describe("prototype path", () => {
  test("1 teacher cohort view", async ({ page }) => {
    await page.goto("/prototype");
    await expect(page).toHaveURL(/\/prototype\/teacher$/);
    await expect(page.getByRole("heading", { name: "Teacher cohort view" })).toBeVisible();
    await expect(page.getByTestId("learner-count")).toHaveText("8");
    await expect(page.getByTestId("bottleneck-name")).toHaveText("Nature of roots and discriminant");
    await expect(page.getByTestId("bottleneck-count")).toHaveText("5 of 8 learners blocked");
    await expect(page.getByTestId("coverage")).toContainText(" of 24");
    // heatmap: label as text in each cell, insufficient evidence marker
    await expect(page.getByTestId(R_CELL)).toContainText("Not mastered");
    await expect(page.getByTestId(R_CELL)).toContainText("3 answers");
    await expect(page.getByTestId("cell-demo-a-equation_formation")).toContainText("Insufficient evidence");
    // bottleneck panel: unreviewed edges, in the warning style, with the words
    const edges = page.getByTestId("edge");
    await expect(edges).toHaveCount(2);
    for (let i = 0; i < 2; i++) {
      await expect(edges.nth(i)).toHaveAttribute("data-review", "proposed");
      await expect(edges.nth(i)).toContainText("proposed, not yet reviewed");
    }
    // teachers have no attempt control
    await expect(page.getByRole("button", { name: /record as/i })).toHaveCount(0);
    await page.getByTestId("col-demo-a").click();
    await expect(page.getByRole("heading", { name: "Learner detail: Learner A" })).toBeVisible();
    await expect(page.getByTestId("primary-action")).toContainText("Review prerequisite");
    await expect(page.getByRole("button", { name: /record as/i })).toHaveCount(0);
    await shot(page, "01_teacher_cohort_light");
    await page.emulateMedia({ colorScheme: "dark" });
    await shot(page, "02_teacher_cohort_dark");
  });

  test("2 learner next step, then 3 an attempt refused because no item is approved", async ({ page, request }) => {
    await page.goto("/prototype/learner/demo-a");
    await expect(page.getByTestId("demo-label")).toHaveText("[DEMO FIXTURE]");
    await expect(page.getByTestId("primary-action")).toHaveText("Review prerequisite: Nature of roots and discriminant");
    await expect(page.getByTestId("reason")).toContainText("is not yet mastered");
    await expect(page.getByTestId("reason")).toContainText("proposed and not yet teacher-reviewed");
    await expect(page.getByTestId("evidence")).toContainText("Algebra of complex numbers: 5 answers");
    await expect(page.getByTestId("policy")).toContainText("policy-v0.1");
    await expect(page.getByTestId("concept-card")).toHaveCount(3);
    await expect(page.getByText("early estimate")).toBeVisible();
    // practice: the bank is not approved, so the API serves no item and the page says so
    await expect(page.getByText("No practice item is available")).toBeVisible();
    await expect(page.getByText(/no approved items yet/)).toBeVisible();
    await expect(page.getByRole("button", { name: /record as/i })).toHaveCount(0);
    await shot(page, "03_learner_next_step");

    // The UI offers no control when nothing is served, so the attempt is sent to the same forwarder the UI uses.
    const attempt = { event_id: "pw-1", concept_id: "jee.math.quadratic_equations.roots_nature", item_id: "roots_nature-easy-0", correct: true };
    const refused = await request.post("/api/proto/as/demo-a/api/prototype/learners/demo-a/events", { data: attempt });
    expect(refused.status()).toBe(422);
    expect(typeof (await refused.json()).detail).toBe("string");
    const asTeacher = await request.post("/api/proto/as/teacher/api/prototype/learners/demo-a/events", { data: attempt });
    expect(asTeacher.status()).toBe(403);
    await page.reload();
    await expect(page.getByTestId("concept-card").nth(1)).toContainText("3 answers");     // state unchanged
    await expect(page.getByTestId("concept-card").nth(1)).toContainText("Not mastered");

    await page.goto("/prototype/learner/demo-b");
    await expect(page.getByTestId("primary-action")).toContainText("Algebra of complex numbers");
    // the two demo learners get different next steps from the same engine
    await expect(page.getByTestId("primary-action")).not.toHaveText("Review prerequisite: Nature of roots and discriminant");
  });

  test("learner screen is closed to non-demo learners", async ({ page }) => {
    await page.goto("/prototype/learner/sim-01");
    await expect(page.locator('.p-state[data-kind="denied"]')).toContainText("Permission denied");
  });

  test("4 evaluation page shows passes and misses in the same style", async ({ page }) => {
    await page.goto("/prototype/evaluation");
    await expect(page.getByRole("heading", { name: "Evaluation" })).toBeVisible();
    const rows = page.getByTestId("eval-row");
    await expect(rows).toHaveCount(32);
    const miss = rows.filter({ has: page.locator('[data-testid="verdict"]', { hasText: "Miss" }) });
    const pass = rows.filter({ has: page.locator('[data-testid="verdict"]', { hasText: "Pass" }) });
    expect(await miss.count()).toBeGreaterThan(0);
    expect(await pass.count()).toBeGreaterThan(0);
    // identical element and class structure for a miss and a pass
    expect(await miss.first().evaluate((e) => e.className + e.tagName)).toBe(await pass.first().evaluate((e) => e.className + e.tagName));
    const named = page.getByTestId("named-miss");
    expect(await named.count()).toBeGreaterThanOrEqual(2);
    await expect(page.getByText("Run 2: post-hoc, not pre-registered")).toBeVisible();
    await expect(page.getByTestId("eval-table").first()).toContainText("[SIM]");
    await shot(page, "04_evaluation");
  });

  test("keyboard focus is visible and no source text leaks", async ({ page }) => {
    await page.goto("/prototype/teacher");
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");
    const outline = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle);
    expect(outline).toBe("solid");
    await expect(page.getByTestId("learner-count")).toBeVisible();
    const text = await page.locator("body").innerText();
    expect(text).not.toMatch(/ASSISTments|JEEBench/i);
    expect(text).not.toMatch(/\b(streak|badge|leaderboard|rank)\b/i);
  });
});

test.describe("phone width", () => {
  for (const [name, url, ready] of [
    ["teacher", "/prototype/teacher", "learner-count"],
    ["learner", "/prototype/learner/demo-a", "primary-action"],
    ["evaluation", "/prototype/evaluation", "eval-table"],
  ] as const) {
    test(`no horizontal page scroll: ${name}`, async ({ page }) => {
      await page.goto(url);
      await expect(page.getByTestId(ready).first()).toBeVisible();
      await noHorizontalScroll(page);
      await shot(page, `05_phone_${name}`);
    });
  }
});
