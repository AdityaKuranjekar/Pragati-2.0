import { expect, test } from "@playwright/test";
import { openApp, resetMock } from "./helpers";

const SCREENS: { path: string; text: RegExp }[] = [
  { path: "/", text: /This week's checklist|इस सप्ताह की चेकलिस्ट/ },
  { path: "/add-data", text: /Spreadsheet|CSV/ },
  { path: "/weak-topics", text: /Topic by topic|विषय-दर-विषय/ },
  { path: "/support", text: /This week|इस सप्ताह/ },
  { path: "/students", text: /Hi |नमस्ते|Not enough data|अभी पर्याप्त/ },
  { path: "/parents", text: /Monthly report|मासिक रिपोर्ट|Not enough data|अभी पर्याप्त/ },
  { path: "/results", text: /Retention by month|माह के अनुसार/ },
  { path: "/privacy", text: /early-warning model may use|अर्ली-वार्निंग/ },
  { path: "/about", text: /./ },
  { path: "/about/data-card", text: /./ },
  { path: "/about/evidence", text: /Model vs your current rule|मॉडल बनाम/ },
];

test.beforeEach(async ({ page }) => resetMock(page));

for (const s of SCREENS) {
  test(`${s.path}: loads offline, no console errors, no sideways scroll`, async ({ page }) => {
    const external: string[] = [];
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/*", (route) => {
      const u = new URL(route.request().url());
      if (["localhost", "127.0.0.1"].includes(u.hostname) || u.protocol === "data:" || u.protocol === "blob:") return route.continue();
      external.push(u.href);
      return route.abort();
    });
    await openApp(page, s.path);
    await expect(page.getByRole("main")).toContainText(s.text, { timeout: 20_000 });
    await page.waitForLoadState("networkidle");
    expect(external, "requests that left the machine").toEqual([]);
    expect(errors.filter((e) => !/Failed to load resource/.test(e)), "console errors").toEqual([]);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(1);
  });
}

// Hindi pass: with the UI in Hindi, long runs of plain English in the main area mean a missed translation.
const ALLOW = /Pragati|Synthetic|synthetic|OMR|CSV|Excel|DigiLocker|AUC|WhatsApp|PDF|JEE|NEET|IRT|ML|ECharts|LightGBM|SHAP|OULAD|ASSISTments|KPI|DPDP|ID|FAQ|ROI|LTV|CAC|SaaS|Rasch|Hindi|English|API|NTA|IIT|MoE|Kota|Patna|Gaya|Lucknow|Raw|Date|Student|Roll|JEE-\S*|PAT\S*|[A-Z]{2,}\S*|\S*\d\S*/g;
// Evidence pages render English-only text from artifact files; for those only the page title is asserted.
const EVIDENCE = ["/about", "/about/data-card", "/about/evidence", "/results"];
for (const s of SCREENS) {
  test(`Hindi pass ${s.path}`, async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("pragati.lang", "hi"));
    await page.goto(s.path);
    await expect(page.getByTestId("page-title")).toHaveText(/[ऀ-ॿ]/);
    await expect(page.getByRole("main")).toContainText(s.text, { timeout: 20_000 });
    await page.waitForTimeout(600);
    if (EVIDENCE.includes(s.path)) return;
    await page.evaluate(() => document.querySelectorAll<HTMLElement>("[data-gap]").forEach((e) => (e.style.display = "none")));
    const text = await page.getByRole("main").innerText();
    const runs = text
      .split("\n")
      .map((l) => l.replace(ALLOW, " ").trim())
      .filter((l) => /(?:[A-Za-z]{3,}\s+){2,}[A-Za-z]{3,}/.test(l));
    expect(runs, "English-only lines found while language is Hindi").toEqual([]);
  });
}

test("server unreachable: calm message with a way to retry, not a blank page", async ({ page }) => {
  await openApp(page);
  await page.route("**/api/**", (r) => r.abort());
  await page.route("http://127.0.0.1:8000/**", (r) => r.abort());
  await page.goto("/results");
  await expect(page.getByRole("alert").first()).toContainText("Cannot reach the server", { timeout: 20_000 });
});
