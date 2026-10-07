/** 42 → "00:42", 68 → "01:08", 600 → "10:00" */
export function mmss(totalSeconds: number | null | undefined): string {
  if (totalSeconds == null || !isFinite(totalSeconds)) return "--:--";
  const s = Math.max(0, Math.round(totalSeconds));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function range(start: number, end: number) {
  return `${mmss(start)}–${mmss(end)}`;
}

const IST: Intl.DateTimeFormatOptions = { timeZone: "Asia/Kolkata" };

export function istTime(iso: string | null | undefined, withSeconds = true): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-IN", {
    ...IST,
    hour: "2-digit",
    minute: "2-digit",
    second: withSeconds ? "2-digit" : undefined,
    hour12: false,
  });
}

export function istDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return (
    new Date(iso).toLocaleString("en-IN", {
      ...IST,
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }) + " IST"
  );
}

export function shortHash(h: string | null | undefined, n = 10) {
  return h ? `${h.slice(0, n)}…` : "—";
}

export function bytes(n: number | null | undefined) {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function pct(v: number | null | undefined, digits = 0) {
  return v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
}

export function geo(lat: number | null | undefined, lon: number | null | undefined) {
  if (lat == null || lon == null) return "Location not captured";
  return `${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E`;
}
