// Recurring issue clusters — GET /trends.
//
// Deliberately NOT a time series. The corpus is four non-contiguous days with a
// 2.5-month gap, so per-day counts reproduce the recording schedule: every
// cluster shows the same ~32/31/8/29 split the corpus does. Four bars that look
// identical across ten issues is a chart that says nothing.
//
// What the data does separate on is outcome quality, and sharply — bill-pay
// resolves at 84% against a 95% baseline, with ~50% higher attention and double
// the handle time. So volume and outcomes lead; the day breakdown stays as a
// small normalised strip, honest about being secondary.
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { getTrends } from "@/lib/api";
import type { TrendingIssue, TrendsBaseline } from "@/lib/types";
import { cn, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

/** Percentage points below baseline resolution before we call it a problem. */
const RESOLUTION_ALERT_GAP = 0.05;

function Metric({
  label,
  value,
  delta,
  worseWhenHigher = false,
}: {
  label: string;
  value: string;
  delta?: number;
  worseWhenHigher?: boolean;
}) {
  const worse =
    delta === undefined
      ? false
      : worseWhenHigher
        ? delta > 0.08
        : delta < -0.02;

  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p
        className={cn(
          "font-mono text-lg tabular-nums",
          worse ? "text-red-600 dark:text-red-400" : "text-slate-800 dark:text-slate-200",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function DayStrip({ issue }: { issue: TrendingIssue }) {
  const days = Object.keys(issue.share_by_day).sort();
  if (days.length === 0) return null;

  // Scaled against this issue's own peak share so over-indexing is visible.
  // Raw counts would just redraw how many calls each day happens to contain.
  const peak = Math.max(...days.map((d) => issue.share_by_day[d]), 0.001);

  return (
    <div className="flex items-end gap-2">
      {days.map((day) => {
        const share = issue.share_by_day[day];
        return (
          <div key={day} className="flex flex-1 flex-col items-center gap-1">
            <span className="font-mono text-[10px] tabular-nums text-slate-400">
              {(share * 100).toFixed(0)}%
            </span>
            <div className="flex h-8 w-full items-end">
              <div
                title={`${day}: ${issue.counts_by_day[day] ?? 0} calls (${(share * 100).toFixed(0)}% of that day)`}
                style={{ height: `${Math.max((share / peak) * 100, 6)}%` }}
                className="w-full rounded-sm bg-blue-500/70"
              />
            </div>
            <span className="font-mono text-[10px] text-slate-400">{day.slice(5)}</span>
          </div>
        );
      })}
    </div>
  );
}

function IssueCard({
  issue,
  baseline,
  maxCalls,
}: {
  issue: TrendingIssue;
  baseline: TrendsBaseline;
  maxCalls: number;
}) {
  const resolutionGap = issue.resolution_rate - baseline.resolution_rate;
  const attentionGap =
    baseline.avg_attention_score > 0
      ? issue.avg_attention_score / baseline.avg_attention_score - 1
      : 0;
  const underperforming = resolutionGap < -RESOLUTION_ALERT_GAP;

  return (
    <li
      className={cn(
        "rounded-lg border p-4 transition",
        underperforming
          ? "border-red-500/50 bg-red-500/5"
          : "border-slate-200 dark:border-slate-800",
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            href={`/trends/${issue.cluster_id}`}
            className="font-medium hover:underline"
          >
            {issue.label}
          </Link>
          {underperforming && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
              <AlertTriangle size={12} />
              resolves {Math.abs(resolutionGap * 100).toFixed(0)}pp below the{" "}
              {(baseline.resolution_rate * 100).toFixed(0)}% average
            </p>
          )}
        </div>
        <Link
          href={`/trends/${issue.cluster_id}`}
          className="shrink-0 font-mono text-sm tabular-nums text-blue-600 hover:underline dark:text-blue-400"
        >
          {issue.call_count} calls →
        </Link>
      </div>

      {/* Volume bar: the primary ranking signal. */}
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <div
          style={{ width: `${(issue.call_count / maxCalls) * 100}%` }}
          className={cn("h-full rounded-full", underperforming ? "bg-red-500" : "bg-blue-500")}
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric
          label="resolved"
          value={`${(issue.resolution_rate * 100).toFixed(0)}%`}
          delta={resolutionGap}
        />
        <Metric
          label="avg attention"
          value={issue.avg_attention_score.toFixed(1)}
          delta={attentionGap}
          worseWhenHigher
        />
        <Metric label="avg handle" value={formatSeconds(issue.avg_handle_time_seconds)} />
        <div className="col-span-2 sm:col-span-1">
          <p className="text-[11px] uppercase tracking-wide text-slate-500">
            share of day
          </p>
          <div className="mt-1">
            <DayStrip issue={issue} />
          </div>
        </div>
      </div>
    </li>
  );
}

function ExceptionCallout({
  issues,
  baseline,
}: {
  issues: TrendingIssue[];
  baseline: TrendsBaseline;
}) {
  /* The list is ranked by volume, which is the right default — but that buries
     the one issue a manager needs to act on below everything that's healthy.
     Surfacing the exceptions here keeps the volume ranking intact underneath. */
  const flagged = issues
    .filter((i) => i.resolution_rate - baseline.resolution_rate < -RESOLUTION_ALERT_GAP)
    .sort((a, b) => a.resolution_rate - b.resolution_rate);

  if (flagged.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-400">
        No issue resolves meaningfully below the{" "}
        {(baseline.resolution_rate * 100).toFixed(0)}% average.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-4">
      <p className="flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-400">
        <AlertTriangle size={15} />
        {flagged.length} issue{flagged.length > 1 ? "s" : ""} resolving below
        average
      </p>
      <ul className="mt-2 space-y-1">
        {flagged.map((issue) => (
          <li key={issue.cluster_id} className="text-sm">
            <Link
              href={`/trends/${issue.cluster_id}`}
              className="font-medium text-red-700 hover:underline dark:text-red-400"
            >
              {issue.label}
            </Link>
            <span className="ml-2 font-mono text-xs tabular-nums text-slate-500">
              {(issue.resolution_rate * 100).toFixed(0)}% vs{" "}
              {(baseline.resolution_rate * 100).toFixed(0)}% · attention{" "}
              {issue.avg_attention_score.toFixed(1)} vs{" "}
              {baseline.avg_attention_score.toFixed(1)} ·{" "}
              {formatSeconds(issue.avg_handle_time_seconds)} vs{" "}
              {formatSeconds(baseline.avg_handle_time_seconds)} ·{" "}
              {issue.call_count} calls →
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}


export default async function TrendsDashboard() {
  const { data, error } = await getTrends();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Trending issues</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Clusters discovered from the call summaries themselves — no predefined
          taxonomy. Ranked by volume, with the outcome metrics that actually
          separate them. Issues resolving below average are flagged.
        </p>
      </div>

      {error && <ApiNotice error={error} />}

      {data && data.issues.length === 0 && (
        <p className="text-sm text-slate-500">
          No clusters yet — run the analysis pipeline.
        </p>
      )}

      {data && data.issues.length > 0 && (
        <>
          <ExceptionCallout issues={data.issues} baseline={data.baseline} />

          <div className="flex flex-wrap gap-6 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900/50">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Baseline, all calls
            </span>
            <span className="font-mono tabular-nums">
              {data.baseline.call_count} calls
            </span>
            <span className="font-mono tabular-nums">
              {(data.baseline.resolution_rate * 100).toFixed(0)}% resolved
            </span>
            <span className="font-mono tabular-nums">
              attention {data.baseline.avg_attention_score.toFixed(1)}
            </span>
            <span className="font-mono tabular-nums">
              {formatSeconds(data.baseline.avg_handle_time_seconds)} avg
            </span>
          </div>

          <ul className="space-y-3">
            {data.issues.map((issue) => (
              <IssueCard
                key={issue.cluster_id}
                issue={issue}
                baseline={data.baseline}
                maxCalls={Math.max(...data.issues.map((i) => i.call_count))}
              />
            ))}
          </ul>

          <p className="text-xs text-slate-400">
            The corpus covers four non-contiguous days, so raw per-day counts
            track the recording schedule rather than any trend. The day strip
            shows each issue&apos;s <em>share</em> of that day&apos;s calls, which is
            comparable across days of very different size.
          </p>
        </>
      )}
    </div>
  );
}
