/**
 * Playwright critical scenarios for Phase 2.
 * Google storage state:
 *   PLAYWRIGHT_E2E=1 PLAYWRIGHT_AUTH_STATE=e2e/.auth/user.json npx playwright test e2e/phase2.spec.ts
 */
import { test, expect } from "@playwright/test";

const base = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const authState = process.env.PLAYWRIGHT_AUTH_STATE;

test.describe("Phase 2 critical", () => {
  test.skip(!process.env.PLAYWRIGHT_E2E, "Set PLAYWRIGHT_E2E=1 with stack running");
  test.skip(!authState, "Set PLAYWRIGHT_AUTH_STATE to a Playwright storage state file (Google login)");

  test.use({ storageState: authState! });

  test("open dashboard", async ({ page }) => {
    await page.goto(`${base}/app`);
    await expect(page).toHaveURL(/\/app/);
    await expect(page.getByRole("heading", { name: /dashboard|welcome/i })).toBeVisible();
  });

  test("create workspace updates dashboard", async ({ page }) => {
    await page.goto(`${base}/app`);
    await page.waitForURL(/\/app/);
    const name = `E2E WS ${Date.now()}`;
    await page.getByRole("button", { name: /create workspace|new workspace|create new/i }).first().click();
    await page.getByPlaceholder(/product knowledge|workspace/i).fill(name);
    await page.getByRole("button", { name: /^create workspace$/i }).click();
    await expect(page.getByText(name).first()).toBeVisible({ timeout: 15000 });
  });

  test("theme dark persists", async ({ page }) => {
    await page.goto(`${base}/app/settings/appearance`);
    await page.getByRole("radio", { name: /dark/i }).click();
    await page.getByRole("button", { name: /^lưu$/i }).click();
    await page.reload();
    await expect(page.locator("html")).toHaveClass(/dark/);
  });
});
