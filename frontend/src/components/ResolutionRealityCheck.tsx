"use client";

import { AlertTriangle } from "lucide-react";
import type { ResolutionContradiction } from "@/lib/types";
import EvidenceChip from "./EvidenceChip";

/**
 * Agent said resolved; the customer's own later words say otherwise. Rule-
 * based (backend/app/pipeline/reality_check.py) — this never fires from an
 * LLM guess, only from a regex hit on both sides plus the same evidence
 * verification every other citation on this page goes through. Rendered only
 * when both quotes exist; there's no "maybe" state to show.
 */
export default function ResolutionRealityCheck({
  contradiction,
}: {
  contradiction: ResolutionContradiction | null;
}) {
  if (!contradiction) return null;

  return (
    <div className="space-y-3 rounded-lg border border-amber-500/50 bg-amber-500/5 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-400">
        <AlertTriangle size={16} />
        Resolution reality check: contradiction found
      </div>
      <p className="text-xs text-slate-500">
        The agent said the issue was resolved. The customer&apos;s own later words say
        otherwise.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Agent claimed
          </p>
          <EvidenceChip evidence={contradiction.agent_evidence} />
        </div>
        <div className="space-y-1.5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Customer said
          </p>
          <EvidenceChip evidence={contradiction.customer_evidence} />
        </div>
      </div>
    </div>
  );
}
