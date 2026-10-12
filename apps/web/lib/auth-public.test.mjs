import assert from "node:assert/strict";
import test from "node:test";

function safeNextPath(next) {
  if (next?.startsWith("/") && !next.startsWith("//")) return next;
  return "/app";
}

function oauthErrorMessage(error) {
  if (!error) return null;
  if (error === "account_suspended") {
    return "Tài khoản của bạn đã bị tạm khóa. Liên hệ quản trị viên nếu cần hỗ trợ.";
  }
  if (error === "oauth_not_configured") {
    return "Đăng nhập Google chưa sẵn sàng. Vui lòng thử lại sau hoặc liên hệ quản trị.";
  }
  return "Không thể đăng nhập bằng Google. Vui lòng thử lại.";
}

test("safeNextPath rejects open redirects", () => {
  assert.equal(safeNextPath("/app/workspaces"), "/app/workspaces");
  assert.equal(safeNextPath("//evil.com"), "/app");
  assert.equal(safeNextPath(undefined), "/app");
});

test("oauthErrorMessage returns Vietnamese copy", () => {
  assert.match(oauthErrorMessage("oauth_not_configured"), /đăng nhập google/i);
  assert.match(oauthErrorMessage("account_suspended"), /tạm khóa/i);
  assert.match(oauthErrorMessage("unknown"), /thử lại/i);
});
