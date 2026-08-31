import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Seconds -> "MM:SS" (or "H:MM:SS" past an hour). Matches the transcript's
 *  evidence timestamps so a chip and a turn read the same way. */
export function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00";
  const s = Math.floor(seconds % 60);
  const m = Math.floor((seconds / 60) % 60);
  const h = Math.floor(seconds / 3600);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** "HH:MM:SS" or "MM:SS" -> seconds, for seeking from an evidence chip. */
export function parseTimestamp(timestamp: string): number {
  const parts = timestamp.split(":").map(Number);
  if (parts.some((n) => !Number.isFinite(n))) return 0;
  return parts.reduce((acc, part) => acc * 60 + part, 0);
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

/** "2 Jun 2020, 01:04" — always UTC, always the same string.
 *
 *  Deliberately NOT `toLocaleString()`. That formats in the *runtime's* locale
 *  and timezone, so the server (a UTC container) and the browser (IST, en-US)
 *  produced different text for the same instant — "2/6/2020, 6:34:32 am" vs
 *  "6/2/2020, 1:04:32 AM" — which React reports as a hydration mismatch and
 *  then re-renders the whole subtree to recover.
 *
 *  Rendering UTC explicitly also removes the day/month ambiguity: these are
 *  2020 call records, and "6/2/2020" meaning two different dates depending on
 *  who is looking is worse than a slightly less familiar format.
 */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${hh}:${mm}`;
}

/** Date only — "2 Jun 2020". Same UTC-fixed reasoning as above. */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** Shared colour ramp for the 0-100 needs-attention score. */
export function attentionTone(score: number | null): string {
  if (score === null) return "border-slate-300 text-slate-500 dark:border-slate-700 dark:text-slate-400";
  if (score >= 75) return "border-red-500/60 text-red-600 bg-red-500/10 dark:text-red-400";
  if (score >= 50) return "border-amber-500/60 text-amber-600 bg-amber-500/10 dark:text-amber-400";
  return "border-emerald-500/60 text-emerald-600 bg-emerald-500/10 dark:text-emerald-400";
}
