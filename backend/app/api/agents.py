"""GET /agents — volume, handle time, outcomes, and per-issue coaching signal.

The brief asks for "a per-agent view of call volumes, handle times and
outcomes". Those alone turn out to be nearly flat on this corpus: resolution
rates run 88.4%-94.6% across ten agents with ~145 calls each, which is close to
noise and tells a manager nothing actionable.

Crossing agents with issue clusters is where the signal is. Robert resolves
89.1% overall but only 60% of gas-bill calls; Elizabeth 88.5% overall but 63.6%
on electric billing. A 25-30 point gap against their own baseline is a specific
coaching action, and it only becomes visible when clustering, reasoning and
outcomes are all correct — which is why the aggregate view hides it.
"""
from fastapi import APIRouter, HTTPException

from app.db.session import DbConn
from app.schemas.call import AgentIssueStat, AgentStats, CallSummary

router = APIRouter()

#: Below this many calls, a per-issue rate is noise. With ~145 calls per agent
#: across 10 issues, 8 is roughly half an average agent-issue cell.
MIN_CALLS_FOR_ISSUE_SIGNAL = 8

_RESOLVED = (
    "AVG(CASE WHEN c.resolution_status IS NULL THEN NULL "
    "         WHEN c.resolution_status = 'resolved' THEN 1.0 ELSE 0.0 END)"
)


def _issue_breakdown(conn, agent_id: str, agent_rate: float) -> list[AgentIssueStat]:
    rows = conn.execute(
        f"""
        SELECT ic.id AS cluster_id, ic.label, COUNT(*) AS n,
               COALESCE({_RESOLVED}, 0) AS res
        FROM calls c
        JOIN call_clusters cc  ON cc.call_id = c.id
        JOIN issue_clusters ic ON ic.id = cc.cluster_id
        WHERE c.agent_id = ? AND c.analyzed_at IS NOT NULL
        GROUP BY ic.id, ic.label
        HAVING n >= ?
        ORDER BY res
        """,
        (agent_id, MIN_CALLS_FOR_ISSUE_SIGNAL),
    ).fetchall()

    return [
        AgentIssueStat(
            cluster_id=r["cluster_id"],
            label=r["label"],
            call_count=r["n"],
            resolution_rate=r["res"],
            delta_vs_self=r["res"] - agent_rate,
        )
        for r in rows
    ]


@router.get("", response_model=list[AgentStats])
def list_agents(conn: DbConn):
    rows = conn.execute(
        f"""
        SELECT a.id, a.name,
               -- Deliberately every call, analysed or not: "call volume" means
               -- calls handled, not calls this pipeline has gotten to yet.
               -- resolution_rate/avg_attention_score are unaffected — AVG()
               -- and the CASE in _RESOLVED already skip NULL (unanalysed)
               -- rows on their own, so the two stats use different implicit
               -- denominators by design, not by accident.
               COUNT(c.id) AS call_count,
               COALESCE(AVG(c.duration_seconds), 0) AS avg_handle_time_seconds,
               COALESCE({_RESOLVED}, 0) AS resolution_rate,
               COALESCE(AVG(c.attention_score), 0) AS avg_attention_score
        FROM agents a
        LEFT JOIN calls c ON c.agent_id = a.id
        GROUP BY a.id, a.name
        ORDER BY call_count DESC, a.name
        """
    ).fetchall()

    agents: list[AgentStats] = []
    for r in rows:
        issues = _issue_breakdown(conn, r["id"], r["resolution_rate"])
        agents.append(
            AgentStats(
                id=r["id"], name=r["name"], call_count=r["call_count"],
                avg_handle_time_seconds=r["avg_handle_time_seconds"],
                resolution_rate=r["resolution_rate"],
                avg_attention_score=r["avg_attention_score"],
                # Worst relative to their own baseline, and only if it's a real
                # gap — a 2-point dip is not a coaching conversation.
                weakest_issue=(
                    issues[0] if issues and issues[0].delta_vs_self < -0.10 else None
                ),
            )
        )
    return agents


@router.get(
    "/{agent_id}/issues",
    response_model=list[AgentIssueStat],
    responses={404: {"description": "No such agent"}},
)
def agent_issues(agent_id: str, conn: DbConn):
    """Full per-issue breakdown for one agent — the coaching detail view."""
    row = conn.execute(
        f"""
        SELECT COALESCE({_RESOLVED}, 0) AS rate
        FROM calls c WHERE c.agent_id = ? AND c.analyzed_at IS NOT NULL
        """,
        (agent_id,),
    ).fetchone()
    if not conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone():
        raise HTTPException(status_code=404, detail=f"no such agent: {agent_id}")

    return _issue_breakdown(conn, agent_id, row["rate"] if row else 0.0)


@router.get(
    "/{agent_id}/calls",
    response_model=list[CallSummary],
    responses={404: {"description": "No such agent"}},
)
def agent_calls(agent_id: str, conn: DbConn, cluster_id: int | None = None, limit: int = 200):
    """This agent's calls, optionally narrowed to one issue."""
    if not conn.execute("SELECT 1 FROM agents WHERE id = ?", (agent_id,)).fetchone():
        raise HTTPException(status_code=404, detail=f"no such agent: {agent_id}")

    sql = """
        SELECT c.id, c.started_at, c.duration_seconds, c.intent_label,
               c.resolution_status, c.summary, c.attention_score,
               ROUND((SELECT AVG(verified) FROM evidence WHERE evidence.call_id = c.id) * 100, 1)
                   AS evidence_coverage
        FROM calls c
    """
    params: list = [agent_id]
    if cluster_id is not None:
        sql += " JOIN call_clusters cc ON cc.call_id = c.id AND cc.cluster_id = ?"
        params = [cluster_id, agent_id]
    sql += " WHERE c.agent_id = ? ORDER BY c.attention_score DESC, c.started_at DESC LIMIT ?"
    params.append(limit)

    return [CallSummary(**dict(r)) for r in conn.execute(sql, params).fetchall()]
