// Per-agent view — GET /agents.
//
// Volume, handle time and outcomes are the brief's ask, but on this corpus they
// barely separate anyone: resolution runs 88.4%-94.6% across ten agents with
// ~145 calls each, which is close to noise.
//
// The signal is agent x ISSUE. Robert resolves 89% overall but only 60% of
// gas-bill calls; Elizabeth 88.5% overall but 64% on electric billing. Comparing
// an agent against their OWN baseline separates "this issue is hard for them"
// from "this agent is weaker", and turns a flat table into a coaching action.
import Link from "next/link";
import { GraduationCap } from "lucide-react";
import { getAgents } from "@/lib/api";
import type { AgentStats } from "@/lib/types";
import { cn, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

function CoachingCallout({ agents }: { agents: AgentStats[] }) {
  const flagged = agents
    .filter((a) => a.weakest_issue)
    .sort((a, b) => a.weakest_issue!.delta_vs_self - b.weakest_issue!.delta_vs_self);

  if (flagged.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4 text-sm">
        <p className="font-medium text-emerald-700 dark:text-emerald-400">
          No agent underperforms their own baseline on any issue
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
      <p className="flex items-center gap-2 font-medium text-amber-700 dark:text-amber-400">
        <GraduationCap size={16} />
        {flagged.length} agent{flagged.length > 1 ? "s" : ""} with a coachable
        issue gap
      </p>
      <ul className="mt-3 space-y-1.5 text-sm">
        {flagged.slice(0, 4).map((a) => {
          const w = a.weakest_issue!;
          return (
            <li key={a.id}>
              <Link
                href={`/agents/${encodeURIComponent(a.id)}`}
                className="font-medium text-amber-700 hover:underline dark:text-amber-400"
              >
                {a.name}
              </Link>{" "}
              <span className="font-mono text-xs text-slate-500">
                resolves {(a.resolution_rate * 100).toFixed(0)}% overall but only{" "}
                <span className="text-red-600 dark:text-red-400">
                  {(w.resolution_rate * 100).toFixed(0)}%
                </span>{" "}
                on {w.label} ({(w.delta_vs_self * 100).toFixed(0)}pp ·{" "}
                {w.call_count} calls)
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default async function AgentsDashboard() {
  const { data: agents, error } = await getAgents();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Agents</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Volume, handle time and outcomes — plus the issue each agent handles
          worst relative to their own baseline, which is where the coachable
          differences actually show up.
        </p>
      </div>

      {error && <ApiNotice error={error} />}

      {agents && agents.length > 0 && (
        <>
          <CoachingCallout agents={agents} />

          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Agent</th>
                  <th className="px-4 py-2.5 font-medium">Calls</th>
                  <th className="px-4 py-2.5 font-medium">Avg handle</th>
                  <th className="px-4 py-2.5 font-medium">Resolved</th>
                  <th className="px-4 py-2.5 font-medium">Avg attention</th>
                  <th className="px-4 py-2.5 font-medium">Weakest issue</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
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
                    <td className="px-4 py-2.5">
                      {a.weakest_issue ? (
                        <span
                          className={cn(
                            "font-mono text-xs",
                            a.weakest_issue.delta_vs_self < -0.2
                              ? "text-red-600 dark:text-red-400"
                              : "text-amber-600 dark:text-amber-400",
                          )}
                        >
                          {a.weakest_issue.label} ·{" "}
                          {(a.weakest_issue.resolution_rate * 100).toFixed(0)}% (
                          {(a.weakest_issue.delta_vs_self * 100).toFixed(0)}pp)
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">
                          consistent across issues
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-slate-400">
            &ldquo;Weakest issue&rdquo; compares an agent against their own
            overall resolution rate, not against other agents, and only counts
            issues with at least 8 calls. Aggregate rates span just 88-95% here,
            so the per-issue view is where coachable differences appear.
          </p>
        </>
      )}
    </div>
  );
}
