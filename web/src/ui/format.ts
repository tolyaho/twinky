export function compact(n: number): string {
  if (n < 1000) return String(n);
  if (n < 10_000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
  if (n < 1_000_000) return Math.round(n / 1000) + "k";
  return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "m";
}

export function pct(x: number): string {
  return Math.round(x * 100) + "%";
}

/** Relative time, compact: "now", "12s", "3m", "1h". */
export function ago(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 3) return "now";
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  if (m < 60) return m + "m";
  return Math.floor(m / 60) + "h";
}

export function clock(ms: number): string {
  const s = Math.floor(ms / 1000);
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${mm}:${String(ss).padStart(2, "0")}`;
}

export const WINDOWS = [
  { ms: 30_000, short: "30s", long: "30 seconds" },
  { ms: 60_000, short: "1m", long: "60 seconds" },
  { ms: 300_000, short: "5m", long: "5 minutes" },
] as const;

export function windowLong(ms: number): string {
  return WINDOWS.find((w) => w.ms === ms)?.long ?? `${Math.round(ms / 1000)} seconds`;
}

export function windowShort(ms: number): string {
  return WINDOWS.find((w) => w.ms === ms)?.short ?? `${Math.round(ms / 1000)}s`;
}

/** Messages per minute from a count over a window of `windowMs`. */
export function perMinute(count: number, windowMs: number): number {
  if (windowMs <= 0) return 0;
  return Math.round((count / windowMs) * 60_000);
}
