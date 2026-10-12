/**
 * Playwright critical scenarios for Phase 7 Pages.
 * Requires PLAYWRIGHT_E2E=1 and PLAYWRIGHT_AUTH_STATE (saved Google session).
 */
import { test, expect } from "@playwright/test";

const base = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const authState = process.env.PLAYWRIGHT_AUTH_STATE;

test.describe("Phase 7 pages", () => {
  test.skip(!process.env.PLAYWRIGHT_E2E, "Set PLAYWRIGHT_E2E=1 with stack running");
  test.skip(!authState, "Set PLAYWRIGHT_AUTH_STATE to a Playwright storage state file (Google login)");

  test.use({ storageState: authState! });

  test("open Pages from a Space", async ({ page }) => {
    await page.goto(`${base}/app/workspaces`);
    await page.waitForURL(/\/app/);
    const firstWs = page.locator('a[href*="/app/workspaces/"]').first();
    await firstWs.click();
    await page.waitForURL(/\/app\/workspaces\/[^/]+/);
    const spacesLink = page.getByRole("link", { name: /spaces/i }).first();
    if (await spacesLink.isVisible()) await spacesLink.click();
    const spaceCard = page.locator('a[href*="/spaces/"]').first();
    await spaceCard.click();
    await page.getByRole("link", { name: /^Pages$/i }).click();
    await expect(page).toHaveURL(/\/pages/);
    await expect(page.getByPlaceholder(/search pages/i)).toBeVisible();
  });
});
