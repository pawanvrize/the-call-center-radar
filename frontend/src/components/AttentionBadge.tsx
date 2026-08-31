"use client";

import type { AttentionFactor } from "@/lib/types";
import { attentionTone, cn } from "@/lib/utils";
import EvidenceChip from "./EvidenceChip";

interface Props {
  score: number | null;
  factors?: AttentionFactor[];
}

/**
 * The 0-100 score is computed in backend/app/pipeline/attention_score.py from
 * documented weights — the LLM only narrates the factors. Showing the factors
 * and their weights alongside the number is what makes it auditable rather
 * than an opaque verdict.
 */
export default function AttentionBadge({ score, factors = [] }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-baseline gap-3">
        <span
          className={cn(
            "rounded-md border px-3 py-1 font-mono text-2xl font-semibold tabular-nums",
            attentionTone(score),
          )}
        >
          {score ?? "—"}
        </span>
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          needs-attention score
        </span>
      </div>

      {factors.length > 0 && (
        <ul className="mt-4 space-y-2">
          {factors.map((f) => (
            <li key={f.factor} className="text-sm">
              <div className="flex items-center gap-2">
                <span className="w-10 shrink-0 font-mono text-xs tabular-nums text-slate-400">
                  {(f.weight * 100).toFixed(0)}%
                </span>
                <span className="flex-1">{f.factor}</span>
              </div>
              {f.evidence && (
                <div className="ml-12 mt-1">
                  <EvidenceChip evidence={f.evidence} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
