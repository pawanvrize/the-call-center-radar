// One customer's full call history — GET /customers/{id}/calls.
import Link from "next/link";
import { getCustomerCalls } from "@/lib/api";
import { attentionTone, cn, formatDateTime, formatSeconds } from "@/lib/utils";
import ApiNotice from "@/components/ApiNotice";

export default async function CustomerDetail({
  params,
}: {
  params: Promise<{ customerId: string }>;
}) {
  const { customerId } = await params;
  const { data: calls, error } = await getCustomerCalls(customerId);

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/customers"
          className="text-sm text-blue-600 hover:underline dark:text-blue-400"
        >
          ← All customers
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">{customerId}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {calls ? `${calls.length} calls` : "Call history"}
        </p>
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
                  <p className="mt-0.5 text-sm text-slate-500">
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
