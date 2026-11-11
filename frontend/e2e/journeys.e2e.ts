import { expect, test } from "@playwright/test";

test("library lists the synthetic corpus with indexing status", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("link", { name: "Halcyon Hub H2 User Manual" })).toBeVisible();
  await expect(page.getByText(/indexed · \d+ passages/).first()).toBeVisible();
  await page.getByRole("navigation", { name: "Collections" }).getByRole("button", { name: /^Engineering/ }).click();
  await expect(page.getByRole("link", { name: "Engineering Guidelines" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Halcyon Hub H2 User Manual" })).toHaveCount(0);
});

test("uploading a markdown document indexes it", async ({ page }) => {
  await page.goto("/library");
  await page.getByRole("button", { name: "Upload" }).click();
  await page.getByLabel("Document file").setInputFiles({ name: "e2e-note.md", mimeType: "text/markdown", buffer: Buffer.from("# E2E Note\nThe loading dock opens at 7 am.\n") });
  await page.getByRole("button", { name: /Add to library/ }).click();
  const row = page.getByRole("link", { name: "E2E Note" }).locator("xpath=ancestor::div[contains(@class,'rounded-2xl')][1]");
  await expect(row).toBeVisible();
  await expect(row.getByText(/indexed · 1 passages/)).toBeVisible();
});

test("research answer cites a passage that opens in the document viewer", async ({ page }) => {
  await page.goto("/studio");
  await page.getByLabel("Research question").fill("How often must service credentials be rotated?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/claims verified|some claims rejected/)).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/rotated every 90 days/).first()).toBeVisible();
  await page.getByRole("button", { name: /Show source P\d/ }).first().click();
  const inspector = page.getByRole("complementary", { name: "Evidence inspector" });
  await expect(inspector.getByRole("heading", { name: "Engineering Guidelines" })).toBeVisible();
  await inspector.getByRole("link", { name: /Open in document viewer/ }).click();
  await expect(page.getByRole("heading", { name: "Engineering Guidelines" })).toBeVisible();
});

test("conflicting policy versions are surfaced with the newer source", async ({ page }) => {
  await page.goto("/studio");
  await page.getByLabel("Research question").fill("What is the refund window and has it changed?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByRole("heading", { name: "Conflicting sources" })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText(/· newer/)).toBeVisible();
});

test("prompt-injection text is quarantined and shown", async ({ page }) => {
  await page.goto("/studio");
  await page.getByLabel("Research question").fill("What discount do authorised partners receive?");
  await page.getByRole("button", { name: "Ask" }).click();
  const inspector = page.getByRole("complementary", { name: "Evidence inspector" });
  await expect(inspector.getByText(/Quarantined text/)).toBeVisible({ timeout: 45_000 });
  await expect(inspector.getByText(/Ignore all previous instructions/)).toBeVisible();
});

test("evidence graph renders recorded relationships", async ({ page }) => {
  await page.goto("/studio");
  await page.getByLabel("Research question").fill("How long does the backup battery keep the hub running?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByText(/claims verified|some claims rejected|abstained/)).toBeVisible({ timeout: 45_000 });
  await page.getByRole("tab", { name: "Evidence graph" }).click();
  await expect(page.locator(".react-flow__node")).not.toHaveCount(0);
  await expect(page.locator(".react-flow__edge").first()).toBeAttached();
});

test("unsafe web URLs are rejected", async ({ request }) => {
  const r = await request.post("/api/documents/web", { data: { url: "http://169.254.169.254/latest/meta-data/" } });
  expect(r.status()).toBe(422);
});
