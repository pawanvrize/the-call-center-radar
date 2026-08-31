// Admin overview — the home page. One screen answering the brief's three
// "across all calls" questions (who needs attention today, what's trending,
// how are agents doing) plus the headline trust number, each linking through
// to its full page rather than duplicating it.
import Link from "next/link";
import { ArrowRight, Headphones, PhoneCall, ShieldCheck, TrendingUp } from "lucide-react";
import { getAgents, getAttention, getRepeatContacts, getTrends } from "@/lib/api";
import { attentionTone, cn, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

/** Matches attentionTone()'s own amber/red boundary — "needs attention" means
 *  the same thing here as the color on every badge across the app. */
const FLAGGED_THRESHOLD = 50;

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {label}
        </p>
        <Icon size={15} className="text-slate-400" />
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold tabular-nums">{value}</p>
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
    <div className="flex items-baseline justify-between">
      <h2 className="text-base font-semibold">{title}</h2>
      <Link
        href={href}
        className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
      >
        {linkLabel} <ArrowRight size={12} />
      </Link>
    </div>
  );
}

export default async function Overview() {
  const [attention, trends, agents, repeats] = await Promise.all([
    getAttention(undefined, 500),
    getTrends(),
    getAgents(),
    getRepeatContacts(),
  ]);

  const errors = [attention.error, trends.error, agents.error, repeats.error].filter(
    (e): e is string => e !== null,
  );

  const flaggedToday =
    attention.data?.calls.filter((c) => (c.attention_score ?? 0) >= FLAGGED_THRESHOLD)
      .length ?? null;

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

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          label="Total calls"
          value={trends.data ? String(trends.data.baseline.call_count) : "—"}
          sub="analysed, precomputed"
          icon={Headphones}
        />
        <StatCard
          label="Needs attention today"
          value={flaggedToday !== null ? String(flaggedToday) : "—"}
          sub={attention.data?.date ? `of ${attention.data.calls.length} on ${attention.data.date}` : undefined}
          icon={ShieldCheck}
        />
        <StatCard
          label="Evidence coverage"
          value={
            attention.data?.evidence_coverage_pct != null
              ? `${attention.data.evidence_coverage_pct}%`
              : "—"
          }
          sub="citations that passed verification"
          icon={TrendingUp}
        />
        <StatCard
          label="Repeat-contact patterns"
          value={repeats.data ? String(repeats.data.length) : "—"}
          sub="customer × issue, 3+ calls"
          icon={PhoneCall}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <SectionHead title="Needs a manager's attention" href="/attention" />
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
