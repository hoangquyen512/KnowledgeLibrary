const TZ = "Asia/Ho_Chi_Minh";

export function isoDate(d: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const year = parts.find((p) => p.type === "year")?.value;
  const month = parts.find((p) => p.type === "month")?.value;
  const day = parts.find((p) => p.type === "day")?.value;
  return `${year}-${month}-${day}`;
}

export function defaultAdminRange(now = new Date()): { from: string; to: string } {
  const to = isoDate(now);
  const [year, month, day] = to.split("-").map(Number);
  const start = new Date(Date.UTC(year, month - 1, day - 6));
  const from = `${start.getUTCFullYear()}-${String(start.getUTCMonth() + 1).padStart(2, "0")}-${String(start.getUTCDate()).padStart(2, "0")}`;
  return { from, to };
}

export function formatRangeLabel(from: string, to: string): string {
  const fmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: TZ });
  const a = fmt.format(new Date(`${from}T00:00:00+07:00`));
  const b = fmt.format(new Date(`${to}T00:00:00+07:00`));
  const [am, ad, ay] = a.replace(",", "").split(" ");
  const [bm, bd, by] = b.replace(",", "").split(" ");
  if (ay === by && am === bm) return `${am} ${ad} – ${bd}, ${ay}`;
  if (ay === by) return `${am} ${ad} – ${bm} ${bd}, ${ay}`;
  return `${a} – ${b}`;
}

export function formatCompactDate(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: TZ,
  }).format(new Date(iso.length <= 10 ? `${iso}T00:00:00+07:00` : iso));
}

export function formatFullDate(iso: string | null): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: TZ,
  }).format(new Date(iso));
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function relativeTime(iso: string, now = new Date()): string {
  const then = new Date(iso).getTime();
  const diff = Math.max(0, now.getTime() - then);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  return formatFullDate(iso);
}

export function queryRange(from: string, to: string): string {
  return `from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
}
