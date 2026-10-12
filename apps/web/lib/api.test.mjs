import test from "node:test";
import assert from "node:assert/strict";

// Lightweight pure helper coverage for CI without a browser.
function publicApiBase(env = process.env) {
  return env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

test("publicApiBase falls back to localhost", () => {
  assert.equal(publicApiBase({}), "http://localhost:8000");
  assert.equal(publicApiBase({ NEXT_PUBLIC_API_URL: "http://api:8000" }), "http://api:8000");
});
