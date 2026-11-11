/** SCREENSHOT_BASE_URL=http://127.0.0.1:3102 npx playwright test — running stack with real models. */
import { expect, test } from "@playwright/test";
import path from "node:path";

const out = (n: string) => path.join(__dirname, "..", "..", "docs", "screenshots", `${n}.png`);

test("capture", async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto("/");
  await page.waitForTimeout(800);
  await page.screenshot({ path: out("01-landing") });
  await page.goto("/library");
  await expect(page.getByRole("link", { name: "Halcyon Hub H2 User Manual" })).toBeVisible();
  await page.waitForTimeout(600);
  await page.screenshot({ path: out("02-library") });
  await page.goto("/studio");
  await page.getByLabel("Research question").fill("What is the current return window for refunds?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/claims verified|some claims rejected|abstained/)).toBeVisible({ timeout: 240_000 });
  await page.getByRole("button", { name: /Show source P\d/ }).first().click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: out("03-research-answer") });
  await page.getByRole("tab", { name: "Evidence graph" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: out("04-evidence-graph") });
  await page.getByRole("complementary", { name: "Evidence inspector" }).getByRole("link", { name: /Open in document viewer/ }).click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: out("05-document-viewer") });
  await page.goto("/library");
  await page.getByRole("link", { name: "Halcyon Hub H2 User Manual" }).click();
  await page.getByRole("button", { name: /Factory reset/ }).first().click();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: out("06-pdf-highlight") });
  await page.goto("/evaluation");
  await page.waitForTimeout(2500);
  await page.screenshot({ path: out("07-evaluation"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/library");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: out("08-mobile-library") });
});
