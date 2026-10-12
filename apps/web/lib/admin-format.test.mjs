import test from "node:test";
import assert from "node:assert/strict";

function isoDateUTC7(d) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const year = parts.find((p) => p.type === "year").value;
  const month = parts.find((p) => p.type === "month").value;
  const day = parts.find((p) => p.type === "day").value;
  return `${year}-${month}-${day}`;
}

function defaultAdminRange(now) {
  const to = isoDateUTC7(now);
  const [year, month, day] = to.split("-").map(Number);
  const start = new Date(Date.UTC(year, month - 1, day - 6));
  const from = `${start.getUTCFullYear()}-${String(start.getUTCMonth() + 1).padStart(2, "0")}-${String(start.getUTCDate()).padStart(2, "0")}`;
  return { from, to };
}

test("default admin range is seven inclusive days", () => {
  const range = defaultAdminRange(new Date("2026-08-27T15:00:00Z"));
  assert.equal(range.to, "2026-08-27");
  assert.equal(range.from, "2026-08-21");
});
