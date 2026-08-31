// Same customer, same issue, again — GET /repeat-contacts.
//
// The brief's own example: "the complaint that came up nine times this week".
// The subtlety is that every customer in this corpus is a repeat caller (all
// 100, averaging 14.4 calls), so "has called before" carries no information.
// Repetition *within one issue cluster* does — and 160 customer-issue pairs
// have three or more calls.
import Link from "next/link";
import { PhoneCall } from "lucide-react";
import { getRepeatContacts } from "@/lib/api";
import { attentionTone, cn, formatDate, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

export default async function RepeatContacts() {
  const { data: repeats, error } = await getRepeatContacts();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Repeat contacts</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Customers who called more than twice about the <em>same</em> issue.
          Matched on issue cluster rather than customer alone — every customer
          here is a repeat caller, so only same-issue repetition means anything.
        </p>
      </div>

      {error && <ApiNotice error={error} />}

      {repeats && repeats.length === 0 && (
        <p className="text-sm text-slate-500">
          No customer called three or more times about one issue.
        </p>
      )}

      {repeats && repeats.length > 0 && (
        <ul className="space-y-3">
          {repeats.map((r) => (
            <li
              key={`${r.customer_id}-${r.cluster_id}`}
              className={cn(
                "rounded-lg border p-4",
                r.unresolved_count > 0
                  ? "border-red-500/40 bg-red-500/5"
                  : "border-slate-200 dark:border-slate-800",
              )}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <p className="font-medium">
                  <PhoneCall size={14} className="mr-1.5 inline text-slate-400" />
                  <Link
                    href={`/customers/${encodeURIComponent(r.customer_id)}`}
                    className="hover:underline"
                  >
                    {r.customer_name}
                  </Link>
                  <span className="text-slate-500"> — </span>
                  <Link
                    href={`/trends/${r.cluster_id}`}
                    className="text-blue-600 hover:underline dark:text-blue-400"
                  >
                    {r.issue_label}
                  </Link>
                </p>
                <p className="font-mono text-sm tabular-nums">
                  <span className="text-lg font-semibold">{r.call_count}</span>
                  <span className="text-slate-500"> calls over {r.span_days}d</span>
                  {r.unresolved_count > 0 && (
                    <span className="ml-2 text-red-600 dark:text-red-400">
                      {r.unresolved_count} unresolved
                    </span>
                  )}
                </p>
              </div>

              {/* The calls themselves — a claim like "8 calls about one card"
                  is only useful if you can open every one of them. */}
              <ol className="mt-3 space-y-1.5">
                {r.calls.map((c, i) => (
                  <li key={c.id} className="flex items-start gap-3 text-sm">
                    <span className="w-5 shrink-0 pt-0.5 font-mono text-xs text-slate-400">
                      {i + 1}.
                    </span>
                    <span
                      className={cn(
                        "shrink-0 rounded border px-1.5 py-0.5 font-mono text-xs tabular-nums",
                        attentionTone(c.attention_score),
                      )}
                    >
                      {c.attention_score ?? "—"}
                    </span>
                    <Link
                      href={`/calls/${encodeURIComponent(c.id)}`}
                      className="min-w-0 flex-1 hover:underline"
                    >
                      <span className="line-clamp-1 text-slate-600 dark:text-slate-300">
                        {c.summary ?? c.intent_label ?? c.id}
                      </span>
                    </Link>
                    <span className="shrink-0 font-mono text-xs text-slate-400">
                      {formatDate(c.started_at)} ·{" "}
                      {formatSeconds(c.duration_seconds)} ·{" "}
                      {c.resolution_status ?? "?"}
                    </span>
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
