/**
 * Playwright E2E critical paths (Google auth storage state).
 * Run: PLAYWRIGHT_E2E=1 PLAYWRIGHT_AUTH_STATE=e2e/.auth/user.json npx playwright test
 */
import { test, expect } from "@playwright/test";

const authState = process.env.PLAYWRIGHT_AUTH_STATE;

test.describe("Auth critical paths", () => {
  test.skip(!process.env.PLAYWRIGHT_E2E, "Set PLAYWRIGHT_E2E=1 with stack running");
  test.skip(!authState, "Set PLAYWRIGHT_AUTH_STATE to a Playwright storage state file (Google login)");

  test.use({ storageState: authState! });

  test("dashboard loads", async ({ page }) => {
    await page.goto("/app");
    await expect(page).toHaveURL(/\/app/);
    await expect(page.getByRole("heading", { name: /dashboard|welcome/i })).toBeVisible();
  });

  test("theme dark persists", async ({ page }) => {
    await page.goto("/app/settings/appearance");
    await page.getByRole("radio", { name: /dark/i }).click();
    await page.getByRole("button", { name: /^lưu$/i }).click();
    await page.reload();
    await expect(page.locator("html")).toHaveClass(/dark/);
  });
});
