/**
 * Adversarial Playwright checks for minimal login (no auth storage state).
 * Run: PLAYWRIGHT_E2E=1 npx playwright test e2e/login-adversarial.spec.ts
 */
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const apiBase = (process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const reportDir = path.join(__dirname, "report", "screenshots");

test.describe("Login adversarial (anonymous)", () => {
  test.skip(!process.env.PLAYWRIGHT_E2E, "Set PLAYWRIGHT_E2E=1 with API + web stack running");

  test.beforeAll(() => {
    fs.mkdirSync(reportDir, { recursive: true });
  });

  test("[TC-ACC-AUTH-001] /login UX, API status parity, no 4xx/5xx", async ({ page }) => {
    const badResponses: string[] = [];
    page.on("response", (resp) => {
      const status = resp.status();
      const url = resp.url();
      if (status >= 400 && (url.includes("/api/") || url.includes("/login"))) {
        badResponses.push(`${status} ${url}`);
      }
    });

    const statusResp = await page.request.get(`${apiBase}/api/v1/auth/status`);
    expect(statusResp.ok(), "API /auth/status must respond 200").toBeTruthy();
    const statusJson = (await statusResp.json()) as { google_configured: boolean };

    await page.goto("/login");
    await expect(page.getByTestId("login-screen")).toBeVisible();
    await expect(page.getByRole("heading", { name: /đăng nhập vào thư viện/i })).toBeVisible();

    const demoLoginApi = await page.request.get(`${apiBase}/api/v1/auth/demo/login`, {
      maxRedirects: 0,
    });
    expect(demoLoginApi.status(), "demo login route must be removed").toBe(404);

    await expect(page.getByText(/demo user|đăng nhập demo/i)).toHaveCount(0);

    const domConfigured = await page.getByTestId("login-screen").getAttribute("data-google-configured");
    expect(domConfigured).toBe(statusJson.google_configured ? "true" : "false");

    await expect(page.getByTestId("login-screen")).toHaveAttribute("data-auth-status-ok", "true");

    const signIn = page.getByTestId("google-sign-in");
    if (statusJson.google_configured) {
      await expect(signIn).not.toHaveAttribute("aria-disabled", "true");
    } else {
      await expect(signIn).toHaveAttribute("aria-disabled", "true");
    }

    expect(badResponses, `No bad API/login responses: ${badResponses.join("; ")}`).toEqual([]);

    await page.screenshot({
      path: path.join(reportDir, "login-default.png"),
      fullPage: true,
    });
  });

  test("[TC-ACC-AUTH-002] OAuth error query shows friendly copy", async ({ page }) => {
    await page.goto("/login?error=oauth_not_configured");
    await expect(page.getByTestId("login-error")).toContainText(/đăng nhập google chưa sẵn sàng/i);
    await page.screenshot({
      path: path.join(reportDir, "login-oauth-error.png"),
      fullPage: true,
    });
  });

  test("[TC-ACC-AUTH-003] / redirects anonymous to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByTestId("login-screen")).toBeVisible();
    await page.screenshot({
      path: path.join(reportDir, "home-redirect-login.png"),
      fullPage: true,
    });
  });

  test("[TC-ACC-AUTH-004] /app without session redirects to login (no 500)", async ({ page }) => {
    const badResponses: string[] = [];
    page.on("response", (resp) => {
      if (resp.status() >= 500) badResponses.push(`${resp.status()} ${resp.url()}`);
    });
    await page.goto("/app");
    await expect(page).toHaveURL(/\/login/);
    expect(badResponses).toEqual([]);
    await page.screenshot({
      path: path.join(reportDir, "app-guard-login.png"),
      fullPage: true,
    });
  });
});
