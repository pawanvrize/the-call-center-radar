"use client";

import { useEffect, useRef } from "react";
import type { Turn } from "@/lib/types";
import { cn, formatSeconds } from "@/lib/utils";
import { usePlayer } from "./PlayerContext";

interface Props {
  turns: Turn[];
  /** The change-point-detected mood shift, marked inline in the transcript. */
  shiftTurnId?: number | null;
}

export default function TranscriptPanel({ turns, shiftTurnId }: Props) {
  const { seekTo, currentTime } = usePlayer();
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeTurn = turns.find(
    (t) => currentTime >= t.start_seconds && currentTime < t.end_seconds,
  );
  const activeId = activeTurn?.id ?? null;

  // Follow playback, but only scroll within the panel — never yank the page.
  useEffect(() => {
    if (activeId === null || !scrollRef.current) return;
    const el = scrollRef.current.querySelector(`[data-turn-id="${activeId}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeId]);

  if (turns.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500 dark:border-slate-700">
        No transcript stored for this call yet — run the ingestion pipeline.
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="max-h-[28rem] overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900"
    >
      {turns.map((turn) => {
        const isActive = turn.id === activeId;
        const isShift = shiftTurnId != null && turn.id === shiftTurnId;
        return (
          <div
            key={turn.id}
            data-turn-id={turn.id}
            onClick={() => seekTo(turn.start_seconds)}
            className={cn(
              "flex cursor-pointer gap-3 border-b border-slate-100 px-4 py-2.5 text-sm transition last:border-b-0 dark:border-slate-900",
              isActive
                ? "bg-blue-500/10"
                : "hover:bg-slate-50 dark:hover:bg-slate-900/50",
              isShift && "border-l-2 border-l-amber-500",
            )}
          >
            <span className="w-12 shrink-0 pt-0.5 font-mono text-xs tabular-nums text-slate-400">
              {formatSeconds(turn.start_seconds)}
            </span>
            <span
              className={cn(
                "w-20 shrink-0 pt-0.5 text-xs font-medium uppercase tracking-wide",
                turn.speaker === "customer"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-slate-500",
              )}
            >
              {turn.speaker}
            </span>
            <p className="min-w-0 flex-1">
              {turn.text}
              {turn.overlapping && (
                <span className="ml-2 rounded bg-slate-200 px-1 py-0.5 font-mono text-[10px] uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  crosstalk
                </span>
              )}
              {isShift && (
                <span className="ml-2 rounded bg-amber-500/20 px-1.5 py-0.5 font-mono text-[10px] uppercase text-amber-700 dark:text-amber-400">
                  ◐ mood shift
                </span>
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}
