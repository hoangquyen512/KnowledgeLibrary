/**
 * Playwright Ask AI smoke test (Google auth storage state).
 */
import { test, expect } from "@playwright/test";

const authState = process.env.PLAYWRIGHT_AUTH_STATE;

test.describe("Ask AI", () => {
  test.skip(!process.env.PLAYWRIGHT_E2E, "Set PLAYWRIGHT_E2E=1 with stack running");
  test.skip(!authState, "Set PLAYWRIGHT_AUTH_STATE to a Playwright storage state file (Google login)");

  test.use({ storageState: authState! });

  test.beforeEach(async ({ page }) => {
    await page.goto("/app/ask");
    await expect(page).toHaveURL(/\/app\/ask/);
  });

  test("ask page renders composer", async ({ page }) => {
    await expect(page.getByPlaceholder(/ask|question|hỏi/i).first()).toBeVisible();
  });
});
