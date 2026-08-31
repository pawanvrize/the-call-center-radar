import type {
  AgentIssueStat,
  AgentStats,
  RepeatContact,
  CallDetail,
  CallSummary,
  Customer,
  AttentionResponse,
  TrendsResponse,
} from "./types";

// On the server we hit FastAPI directly — a server component going back out
// through Next's own rewrite would be a pointless extra hop. In the browser we
// use the relative /api path, which next.config.ts rewrites to the backend, so
// there is no CORS surface at all.
function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.BACKEND_URL ?? "http://localhost:8000";
  }
  return "/api";
}

export type ApiResult<T> =
  | { data: T; error: null }
  | { data: null; error: string };

/**
 * Every endpoint in backend/app/api/ currently returns 501 — the pipeline that
 * fills the database isn't written yet. So this never throws: it reports the
 * failure and lets the page render an honest empty state instead of a crash.
 * Once the backend is real, the same call path just starts returning data.
 */
export async function apiGet<T>(
  path: string,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${apiBase()}${path}`, {
      // The analysis is precomputed and immutable between pipeline runs, but
      // during the build week we always want what's actually in SQLite.
      cache: "no-store",
      ...init,
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return {
        data: null,
        error:
          res.status === 501
            ? `Not implemented yet on the backend (${path})`
            : `${res.status} ${res.statusText} — ${detail.slice(0, 200)}`,
      };
    }

    return { data: (await res.json()) as T, error: null };
  } catch (e) {
    return {
      data: null,
      error: `Could not reach the API at ${apiBase()}${path} — ${
        e instanceof Error ? e.message : String(e)
      }`,
    };
  }
}

export const getCustomers = () => apiGet<Customer[]>("/customers");

export const getCustomerCalls = (customerId: string) =>
  apiGet<CallSummary[]>(`/customers/${encodeURIComponent(customerId)}/calls`);

export const getCall = (callId: string) =>
  apiGet<CallDetail>(`/calls/${encodeURIComponent(callId)}`);

export const getAttention = (date?: string, limit?: number) => {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  if (limit) params.set("limit", String(limit));
  const qs = params.toString();
  return apiGet<AttentionResponse>(`/attention${qs ? `?${qs}` : ""}`);
};

export const getTrends = () => apiGet<TrendsResponse>("/trends");

export const getClusterCalls = (clusterId: number) =>
  apiGet<CallSummary[]>(`/trends/${clusterId}/calls`);

export const getAgents = () => apiGet<AgentStats[]>("/agents");

export const getAgentIssues = (agentId: string) =>
  apiGet<AgentIssueStat[]>(`/agents/${encodeURIComponent(agentId)}/issues`);

export const getAgentCalls = (agentId: string, clusterId?: number) =>
  apiGet<CallSummary[]>(
    `/agents/${encodeURIComponent(agentId)}/calls` +
      (clusterId != null ? `?cluster_id=${clusterId}` : ""),
  );

export const getRepeatContacts = () =>
  apiGet<RepeatContact[]>("/repeat-contacts");
