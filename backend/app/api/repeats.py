"""GET /repeat-contacts — the same customer, calling again about the same issue.

Straight from the brief's problem statement: "the complaint that came up nine
times this week". The subtlety is that in this corpus *every* customer is a
repeat caller — all 100 of them, averaging 14.4 calls — so "has called before"
carries no information at all.

What carries information is repetition **within one issue cluster**. 160
customer-issue pairs have three or more calls; James Williams has eight about a
single card replacement. That is a genuine unresolved-problem signal, and it
falls out of the clustering for free.
"""
from fastapi import APIRouter

from app.db.session import DbConn
from app.schemas.call import CallSummary, RepeatContact

router = APIRouter()

#: Two calls about the same topic is a follow-up. Three is a pattern.
MIN_CALLS = 3


@router.get("", response_model=list[RepeatContact])
def repeat_contacts(conn: DbConn, min_calls: int = MIN_CALLS, limit: int = 50):
    groups = conn.execute(
        """
        SELECT c.customer_id, cu.name AS customer_name,
               cc.cluster_id, ic.label AS issue_label,
               COUNT(*) AS n,
               -- 'partial' counts too: a customer whose card-decline issue was
               -- called "partially resolved" four times running is exactly the
               -- unresolved-problem signal this view exists to surface. Only
               -- strict 'unresolved' was counted originally, which silently
               -- dropped every partial-resolution repeat pattern from both this
               -- count and the ORDER BY below.
               SUM(CASE WHEN c.resolution_status IN ('unresolved', 'partial') THEN 1 ELSE 0 END) AS unresolved,
               MIN(c.started_at) AS first_call,
               MAX(c.started_at) AS last_call,
               julianday(MAX(c.started_at)) - julianday(MIN(c.started_at)) AS span
        FROM call_clusters cc
        JOIN calls c           ON c.id = cc.call_id
        JOIN customers cu      ON cu.id = c.customer_id
        JOIN issue_clusters ic ON ic.id = cc.cluster_id
        GROUP BY c.customer_id, cc.cluster_id
        HAVING n >= ?
        -- Most-repeated first, then most-unresolved: a customer who called five
        -- times and still isn't sorted outranks one who called five times and was.
        ORDER BY n DESC, unresolved DESC
        LIMIT ?
        """,
        (min_calls, limit),
    ).fetchall()

    results: list[RepeatContact] = []
    for g in groups:
        calls = conn.execute(
            """
            SELECT c.id, c.started_at, c.duration_seconds, c.intent_label,
                   c.resolution_status, c.summary, c.attention_score,
                   ROUND((SELECT AVG(verified) FROM evidence WHERE evidence.call_id = c.id) * 100, 1)
                       AS evidence_coverage
            FROM call_clusters cc
            JOIN calls c ON c.id = cc.call_id
            WHERE c.customer_id = ? AND cc.cluster_id = ?
            ORDER BY c.started_at
            """,
            (g["customer_id"], g["cluster_id"]),
        ).fetchall()

        results.append(
            RepeatContact(
                customer_id=g["customer_id"],
                customer_name=g["customer_name"],
                cluster_id=g["cluster_id"],
                issue_label=g["issue_label"],
                call_count=g["n"],
                unresolved_count=g["unresolved"] or 0,
                first_call_at=g["first_call"],
                last_call_at=g["last_call"],
                span_days=round(g["span"] or 0.0, 1),
                calls=[CallSummary(**dict(r)) for r in calls],
            )
        )
    return results
