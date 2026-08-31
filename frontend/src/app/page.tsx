// Admin overview — the home page. One screen answering the brief's three
// "across all calls" questions (who needs attention today, what's trending,
// how are agents doing) plus the headline trust number, each linking through
// to its full page rather than duplicating it.
//
// Built to be scanned, not read: the one number that actually needs a
// decision (critical calls today) gets a status banner of its own, with
// color carrying the verdict before anyone reads a digit. Everything below
// it is a preview, three rows deep, existing purely to justify the banner.
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Headphones,
  PhoneCall,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { getAgents, getAttention, getRepeatContacts, getTrends } from "@/lib/api";
import { attentionTone, cn, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

/** Matches attentionTone()'s own boundaries, so a color here means the same
 *  thing it means on every badge elsewhere in the app. */
const CRITICAL_THRESHOLD = 75;
const FLAGGED_THRESHOLD = 50;

type Tone = "neutral" | "good" | "warning" | "critical";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-slate-800 dark:text-slate-100",
  good: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  critical: "text-red-600 dark:text-red-400",
};
const TONE_DOT: Record<Tone, string> = {
  neutral: "bg-slate-300 dark:bg-slate-600",
  good: "bg-emerald-500",
  warning: "bg-amber-500",
  critical: "bg-red-500",
};

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  tone?: Tone;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <span className={cn("h-1.5 w-1.5 rounded-full", TONE_DOT[tone])} />
          {label}
        </p>
        <Icon size={15} className="text-slate-400" />
      </div>
      <p className={cn("mt-2 font-mono text-2xl font-semibold tabular-nums", TONE_TEXT[tone])}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function SectionHead({
  title,
  href,
  linkLabel = "View all",
}: {
  title: string;
  href: string;
  linkLabel?: string;
}) {
  return (
    <div className="flex items-baseline justify-between border-b border-slate-200 pb-2 dark:border-slate-800">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
        {title}
      </h2>
      <Link
        href={href}
        className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
      >
        {linkLabel} <ArrowRight size={12} />
      </Link>
    </div>
  );
}

export default async function Overview({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  const [attention, trends, agents, repeats] = await Promise.all([
    getAttention(date, 500),
    getTrends(),
    getAgents(),
    getRepeatContacts(),
  ]);

  const errors = [attention.error, trends.error, agents.error, repeats.error].filter(
    (e): e is string => e !== null,
  );

  const todaysCalls = attention.data?.calls ?? [];
  const criticalCount = todaysCalls.filter(
    (c) => (c.attention_score ?? 0) >= CRITICAL_THRESHOLD,
  ).length;
  const flaggedCount = todaysCalls.filter(
    (c) => (c.attention_score ?? 0) >= FLAGGED_THRESHOLD,
  ).length;
  const topScore = todaysCalls.reduce((max, c) => Math.max(max, c.attention_score ?? 0), 0);

  const attentionToneCard: Tone = criticalCount > 0 ? "critical" : flaggedCount > 0 ? "warning" : "good";

  const coveragePct = attention.data?.evidence_coverage_pct ?? null;
  const coverageTone: Tone =
    coveragePct == null ? "neutral" : coveragePct >= 85 ? "good" : coveragePct >= 70 ? "warning" : "critical";

  const unresolvedRepeats = repeats.data?.filter((r) => r.unresolved_count > 0).length ?? 0;
  const repeatsTone: Tone = unresolvedRepeats > 0 ? "warning" : (repeats.data?.length ?? 0) > 0 ? "neutral" : "good";

  const topIssues = trends.data
    ? [...trends.data.issues]
        .sort((a, b) => {
          const gapA = a.resolution_rate - trends.data!.baseline.resolution_rate;
          const gapB = b.resolution_rate - trends.data!.baseline.resolution_rate;
          // Underperforming issues first, then by volume — the same priority
          // the trends page itself gives them, just compressed to 4 rows.
          if ((gapA < -0.05) !== (gapB < -0.05)) return gapA < -0.05 ? -1 : 1;
          return b.call_count - a.call_count;
        })
        .slice(0, 4)
    : [];

  const topAgents = agents.data
    ? [...agents.data].sort((a, b) => b.call_count - a.call_count).slice(0, 5)
    : [];

  // So "View all"/"Review" links land on the same day already picked here,
  // instead of resetting to the latest one.
  const attentionHref = attention.data?.date ? `/attention?date=${attention.data.date}` : "/attention";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Every recorded call, reduced to what a manager needs to act on today —
          each number below opens to the citation behind it.
        </p>
      </div>

      {errors.length > 0 && <ApiNotice error={errors[0]} />}

      {/* The corpus covers four non-contiguous days, so "today" defaults to
          the most recent one with calls rather than the literal date — same
          convention as /attention. The banner and the two day-scoped stat
          cards below all follow whichever day is picked here; Trending
          issues and Agent snapshot stay corpus-wide, since those endpoints
          have no notion of a day at all. */}
      {attention.data && attention.data.available_dates.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-slate-500">Day</span>
          {attention.data.available_dates.map((day) => {
            const active = day.date === attention.data!.date;
            return (
              <Link
                key={day.date}
                href={`/?date=${day.date}`}
                className={cn(
                  "rounded-md border px-3 py-1 font-mono text-xs tabular-nums transition",
                  active
                    ? "border-blue-500 bg-blue-500/10 text-blue-600 dark:text-blue-400"
                    : "border-slate-200 text-slate-500 hover:border-blue-400 dark:border-slate-800",
                )}
              >
                {day.date}
                <span className="ml-2 text-slate-400">{day.call_count}</span>
              </Link>
            );
          })}
        </div>
      )}

      {/* The one verdict this page exists to deliver, stated before any
          number is read — color and words agree, never color alone. */}
      {attention.data &&
        (criticalCount > 0 ? (
          <div className="flex items-center gap-3 rounded-lg border border-red-500/40 bg-red-500/5 p-4">
            <AlertTriangle size={18} className="shrink-0 text-red-600 dark:text-red-400" />
            <p className="text-sm">
              <span className="font-semibold text-red-700 dark:text-red-400">
                {criticalCount} call{criticalCount > 1 ? "s" : ""} scored 75+
              </span>{" "}
              <span className="text-slate-600 dark:text-slate-400">
                and need review today ({attention.data.date}).
              </span>
            </p>
            <Link
              href={attentionHref}
              className="ml-auto shrink-0 flex items-center gap-1 text-sm font-medium text-red-700 hover:underline dark:text-red-400"
            >
              Review now <ArrowRight size={14} />
            </Link>
          </div>
        ) : flaggedCount > 0 ? (
          <div className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
            <AlertTriangle size={18} className="shrink-0 text-amber-600 dark:text-amber-400" />
            <p className="text-sm">
              <span className="font-semibold text-amber-700 dark:text-amber-400">
                {flaggedCount} call{flaggedCount > 1 ? "s" : ""} worth a look
              </span>{" "}
              <span className="text-slate-600 dark:text-slate-400">
                today ({attention.data.date}) — none critical yet.
              </span>
            </p>
            <Link
              href={attentionHref}
              className="ml-auto shrink-0 flex items-center gap-1 text-sm font-medium text-amber-700 hover:underline dark:text-amber-400"
            >
              Review <ArrowRight size={14} />
            </Link>
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4">
            <CheckCircle2 size={18} className="shrink-0 text-emerald-600 dark:text-emerald-400" />
            <p className="text-sm">
              <span className="font-semibold text-emerald-700 dark:text-emerald-400">
                Nothing urgent today
              </span>{" "}
              <span className="text-slate-600 dark:text-slate-400">
                ({attention.data.date}) — highest score is {topScore || "—"}.
              </span>
            </p>
          </div>
        ))}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Total calls"
          value={trends.data ? String(trends.data.baseline.call_count) : "—"}
          sub="analysed, precomputed"
          icon={Headphones}
        />
        <StatCard
          label="Critical today"
          value={attention.data ? String(criticalCount) : "—"}
          sub={attention.data ? `${flaggedCount} flagged of ${todaysCalls.length}` : undefined}
          icon={ShieldCheck}
          tone={attentionToneCard}
        />
        <StatCard
          label="Evidence coverage"
          value={coveragePct != null ? `${coveragePct}%` : "—"}
          sub="citations that passed verification"
          icon={TrendingUp}
          tone={coverageTone}
        />
        <StatCard
          label="Repeat-contact patterns"
          value={repeats.data ? String(repeats.data.length) : "—"}
          sub={repeats.data ? `${unresolvedRepeats} with an unresolved call` : "customer × issue, 3+ calls"}
          icon={PhoneCall}
          tone={repeatsTone}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <SectionHead title="Needs a manager's attention" href={attentionHref} />
          {attention.data && attention.data.calls.length === 0 && (
            <p className="text-sm text-slate-500">No calls for this day.</p>
          )}
          <ul className="space-y-2">
            {attention.data?.calls.slice(0, 5).map((call) => (
              <li key={call.id}>
                <Link
                  href={`/calls/${encodeURIComponent(call.id)}`}
                  className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm transition hover:border-blue-400 hover:shadow-md dark:border-slate-700 dark:bg-slate-800"
                >
                  <span
                    className={cn(
                      "shrink-0 rounded-md border px-2 py-1 font-mono text-sm font-semibold tabular-nums",
                      attentionTone(call.attention_score),
                    )}
                  >
                    {call.attention_score ?? "—"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {call.intent_label ?? "Intent not analysed"}
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">
                      {call.summary ?? "No summary stored."}
                    </p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-3">
          <SectionHead title="Trending issues" href="/trends" />
          {trends.data && trends.data.issues.length === 0 && (
            <p className="text-sm text-slate-500">No clusters yet.</p>
          )}
          <ul className="space-y-2">
            {topIssues.map((issue) => {
              const gap = issue.resolution_rate - (trends.data?.baseline.resolution_rate ?? 0);
              const underperforming = gap < -0.05;
              return (
                <li key={issue.cluster_id}>
                  <Link
                    href={`/trends/${issue.cluster_id}`}
                    className={cn(
                      "flex items-center justify-between gap-3 rounded-xl border p-3 shadow-sm transition hover:shadow-md",
                      underperforming
                        ? "border-red-500/40 bg-red-500/5 hover:border-red-400"
                        : "border-slate-200 bg-white hover:border-blue-400 dark:border-slate-700 dark:bg-slate-800",
                    )}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{issue.label}</p>
                      <p
                        className={cn(
                          "mt-0.5 font-mono text-xs tabular-nums",
                          underperforming
                            ? "text-red-600 dark:text-red-400"
                            : "text-slate-500",
                        )}
                      >
                        {(issue.resolution_rate * 100).toFixed(0)}% resolved
                        {underperforming ? " · below average" : ""}
                      </p>
                    </div>
                    <span className="shrink-0 font-mono text-xs tabular-nums text-slate-400">
                      {issue.call_count} calls
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <div className="space-y-3">
        <SectionHead title="Agent snapshot" href="/agents" />
        {agents.data && agents.data.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Agent</th>
                  <th className="px-4 py-2.5 font-medium">Calls</th>
                  <th className="px-4 py-2.5 font-medium">Avg handle</th>
                  <th className="px-4 py-2.5 font-medium">Resolved</th>
                  <th className="px-4 py-2.5 font-medium">Avg attention</th>
                </tr>
              </thead>
              <tbody>
                {topAgents.map((a) => (
                  <tr
                    key={a.id}
                    className="border-b border-slate-100 last:border-b-0 hover:bg-slate-50 dark:border-slate-900 dark:hover:bg-slate-900/50"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/agents/${encodeURIComponent(a.id)}`}
                        className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                      >
                        {a.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">{a.call_count}</td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {formatSeconds(a.avg_handle_time_seconds)}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {(a.resolution_rate * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {a.avg_attention_score.toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
