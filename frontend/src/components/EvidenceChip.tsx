"use client";

import { AlertTriangle, Quote } from "lucide-react";
import type { Evidence } from "@/lib/types";
import { parseTimestamp } from "@/lib/utils";
import { usePlayer } from "./PlayerContext";

/**
 * The rubric, made interactive. "A claim with no evidence scores zero" — so a
 * claim without an Evidence renders as an explicit gap, never as a bare
 * assertion. A claim whose quote failed the fuzzy-match verifier renders as
 * unverified rather than being silently shown as fact.
 */
export default function EvidenceChip({ evidence }: { evidence: Evidence | null }) {
  const { seekTo } = usePlayer();

  if (!evidence) {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-dashed border-slate-300 px-2 py-0.5 font-mono text-xs text-slate-400 dark:border-slate-700">
        no evidence
      </span>
    );
  }

  const { timestamp, quote, verified } = evidence;

  return (
    <button
      type="button"
      onClick={() => seekTo(parseTimestamp(timestamp))}
      title={`${verified ? "Verified" : "UNVERIFIED"} — "${quote}"`}
      className={
        "inline-flex max-w-full items-center gap-1.5 rounded border px-2 py-0.5 text-left font-mono text-xs transition hover:brightness-110 " +
        (verified
          ? "border-blue-500/50 bg-blue-500/10 text-blue-700 dark:text-blue-300"
          : "border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-400")
      }
    >
      {verified ? <Quote size={11} /> : <AlertTriangle size={11} />}
      <span className="tabular-nums">{timestamp}</span>
      <span className="truncate font-sans italic opacity-80">“{quote}”</span>
    </button>
  );
}
