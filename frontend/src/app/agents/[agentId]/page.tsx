// One agent's full per-issue breakdown — the coaching detail view.
import Link from "next/link";
import { getAgentIssues, getAgents } from "@/lib/api";
import { cn } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

export default async function AgentDetail({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  const { agentId } = await params;
  const [{ data: issues, error }, { data: agents }] = await Promise.all([
    getAgentIssues(agentId),
    getAgents(),
  ]);
  const agent = agents?.find((a) => a.id === agentId);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/agents"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← All agents
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">{agent?.name ?? agentId}</h1>
        {agent && (
          <p className="mt-1 font-mono text-sm text-slate-500">
            {agent.call_count} calls ·{" "}
            {(agent.resolution_rate * 100).toFixed(1)}% resolved overall ·
            attention {agent.avg_attention_score.toFixed(1)}
          </p>
        )}
      </div>

      {error && <ApiNotice error={error} />}

      {issues && issues.length > 0 && agent && (
        <>
          <p className="text-sm text-slate-500">
            Each bar is this agent&apos;s resolution rate on one issue, against
            their own {(agent.resolution_rate * 100).toFixed(0)}% overall
            baseline (the dashed line).
          </p>

          <ul className="space-y-3">
            {issues.map((issue) => {
              const gap = issue.delta_vs_self;
              const weak = gap < -0.1;
              return (
                <li
                  key={issue.cluster_id}
                  className={cn(
                    "rounded-lg border p-4",
                    weak
                      ? "border-red-500/40 bg-red-500/5"
                      : "border-slate-200 dark:border-slate-800",
                  )}
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <Link
                      href={`/trends/${issue.cluster_id}`}
                      className="font-medium hover:underline"
                    >
                      {issue.label}
                    </Link>
                    <span className="shrink-0 font-mono text-sm tabular-nums">
                      {(issue.resolution_rate * 100).toFixed(0)}%
                      <span
                        className={cn(
                          "ml-2 text-xs",
                          weak
                            ? "text-red-600 dark:text-red-400"
                            : "text-slate-400",
                        )}
                      >
                        {gap >= 0 ? "+" : ""}
                        {(gap * 100).toFixed(0)}pp
                      </span>
                    </span>
                  </div>

                  {/* Bar with the agent's own baseline marked, so the gap is
                      visible without doing arithmetic. */}
                  <div className="relative mt-3 h-2 w-full rounded-full bg-slate-200 dark:bg-slate-800">
                    <div
                      style={{ width: `${issue.resolution_rate * 100}%` }}
                      className={cn(
                        "h-full rounded-full",
                        weak ? "bg-red-500" : "bg-blue-500",
                      )}
                    />
                    <div
                      style={{ left: `${agent.resolution_rate * 100}%` }}
                      title={`this agent's overall rate: ${(agent.resolution_rate * 100).toFixed(0)}%`}
                      className="absolute -top-1 h-4 border-l-2 border-dashed border-slate-500"
                    />
                  </div>

                  <p className="mt-2 font-mono text-xs text-slate-400">
                    {issue.call_count} calls
                  </p>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {issues && issues.length === 0 && (
        <p className="text-sm text-slate-500">
          No issue has at least 8 calls for this agent — not enough data to
          judge per-issue performance.
        </p>
      )}
    </div>
  );
}
