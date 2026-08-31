// The calls behind one issue cluster — GET /trends/{id}/calls.
//
// "179 appointment calls" is only a useful finding if you can open them. Ranked
// worst-first by attention score, so the reason an issue was flagged is the
// first thing on screen.
import Link from "next/link";
import { getClusterCalls, getTrends } from "@/lib/api";
import { attentionTone, cn, formatDateTime, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

export default async function ClusterCalls({
  params,
}: {
  params: Promise<{ clusterId: string }>;
}) {
  const { clusterId } = await params;
  const id = Number(clusterId);

  const [{ data: calls, error }, { data: trends }] = await Promise.all([
    getClusterCalls(id),
    getTrends(),
  ]);
  const issue = trends?.issues.find((i) => i.cluster_id === id);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/trends"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← All issues
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">
          {issue?.label ?? `Cluster ${clusterId}`}
        </h1>
        {issue && (
          <p className="mt-1 font-mono text-sm text-slate-500">
            {issue.call_count} calls ·{" "}
            {(issue.resolution_rate * 100).toFixed(0)}% resolved · attention{" "}
            {issue.avg_attention_score.toFixed(1)} ·{" "}
            {formatSeconds(issue.avg_handle_time_seconds)} avg
          </p>
        )}
      </div>

      {error && <ApiNotice error={error} />}

      {calls && calls.length > 0 && (
        <ul className="space-y-2">
          {calls.map((call) => (
            <li key={call.id}>
              <Link
                href={`/calls/${encodeURIComponent(call.id)}`}
                className="flex items-start gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-400 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
              >
                <span
                  className={cn(
                    "shrink-0 rounded-md border px-2 py-0.5 font-mono text-sm tabular-nums",
                    attentionTone(call.attention_score),
                  )}
                >
                  {call.attention_score ?? "—"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-medium">
                    {call.intent_label ?? "Intent not analysed"}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-sm text-slate-500">
                    {call.summary ?? "No summary stored."}
                  </p>
                  <p className="mt-1 font-mono text-xs text-slate-400">
                    {formatDateTime(call.started_at)} ·{" "}
                    {formatSeconds(call.duration_seconds)} ·{" "}
                    {call.resolution_status ?? "unknown"}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
