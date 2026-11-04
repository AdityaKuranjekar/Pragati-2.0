// Screenshots of every page at three widths and two languages: node scripts/shots.mjs <baseUrl> <outDir>
import { chromium } from "@playwright/test";
import fs from "node:fs";

const base = process.argv[2] ?? "http://localhost:3101";
const out = process.argv[3] ?? "screenshots/after";
fs.mkdirSync(out, { recursive: true });
const pages = [["home", "/"], ["add-data", "/add-data"], ["weak-topics", "/weak-topics"], ["support", "/support"], ["students", "/students"], ["parents", "/parents"], ["results", "/results"], ["privacy", "/privacy"], ["about", "/about"], ["evidence", "/about/evidence"]];
const sizes = [["1280", 1280, 900], ["768", 768, 1000], ["375", 375, 800]];
const browser = await chromium.launch();
for (const lang of ["en", "hi"]) {
  for (const [sn, w, h] of sizes) {
    if (lang === "hi" && sn === "768") continue;
    const ctx = await browser.newContext({ viewport: { width: w, height: h } });
    await ctx.addInitScript((l) => localStorage.setItem("pragati.lang", l), lang);
    const page = await ctx.newPage();
    for (const [name, path] of pages) {
      await page.goto(base + path);
      await page.waitForSelector('[data-testid="page-title"]');
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${out}/${name}-${sn}-${lang}.png`, fullPage: true });
    }
    await ctx.close();
  }
}
await browser.close();
console.log("done", out);
