"""GET /trends — recurring issue clusters, ranked by what the data supports.

This corpus spans four non-contiguous days (2020-03-15, 05-30, 06-01, 06-02)
with a 2.5-month gap. Per-day call counts therefore reproduce the *recording
schedule*, not any trend: every cluster shows the same 32/31/8/29 split as the
corpus overall, because that is how many calls exist on each day. Presenting
that as a trend line would be four bars that say nothing.

What the data does support is outcome quality, and it is genuinely
discriminating — bill-pay calls resolve at 84% against a 95% baseline, score
~50% higher on attention, and run roughly double the handle time. So this
endpoint returns resolution rate, attention and handle time alongside volume,
plus a corpus baseline to compare against, and normalises the per-day figures
to share-of-day so over-indexing is visible rather than drowned out.
"""
from fastapi import APIRouter, HTTPException

from app.db.session import DbConn
from app.schemas.call import CallSummary, TrendingIssue, TrendsBaseline, TrendsResponse

router = APIRouter()


@router.get("", response_model=TrendsResponse)
def trending_issues(conn: DbConn, limit: int = 25):
    base = conn.execute(
        """
        SELECT COUNT(*) AS n,
               COALESCE(AVG(CASE WHEN resolution_status = 'resolved' THEN 1.0
                                 WHEN resolution_status IS NULL THEN NULL
                                 ELSE 0.0 END), 0) AS res,
               COALESCE(AVG(attention_score), 0)   AS attn,
               COALESCE(AVG(duration_seconds), 0)  AS dur
        FROM calls WHERE analyzed_at IS NOT NULL
        """
    ).fetchone()

    # Denominator for share-of-day: how many analysed calls exist per day.
    day_totals = {
        r["day"]: r["n"]
        for r in conn.execute(
            """
            SELECT DATE(started_at) AS day, COUNT(*) AS n
            FROM calls WHERE analyzed_at IS NOT NULL GROUP BY day
            """
        )
    }

    clusters = conn.execute(
        """
        SELECT ic.id AS cluster_id, ic.label,
               COUNT(*) AS call_count,
               COALESCE(AVG(CASE WHEN c.resolution_status = 'resolved' THEN 1.0
                                 WHEN c.resolution_status IS NULL THEN NULL
                                 ELSE 0.0 END), 0) AS res,
               COALESCE(AVG(c.attention_score), 0)  AS attn,
               COALESCE(AVG(c.duration_seconds), 0) AS dur
        FROM issue_clusters ic
        JOIN call_clusters cc ON cc.cluster_id = ic.id
        JOIN calls c          ON c.id = cc.call_id
        GROUP BY ic.id, ic.label
        ORDER BY call_count DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    issues: list[TrendingIssue] = []
    for cluster in clusters:
        days = conn.execute(
            """
            SELECT DATE(c.started_at) AS day, COUNT(*) AS n
            FROM call_clusters cc
            JOIN calls c ON c.id = cc.call_id
            WHERE cc.cluster_id = ?
            GROUP BY day ORDER BY day
            """,
            (cluster["cluster_id"],),
        ).fetchall()

        counts = {r["day"]: r["n"] for r in days}
        issues.append(
            TrendingIssue(
                cluster_id=cluster["cluster_id"],
                label=cluster["label"],
                call_count=cluster["call_count"],
                counts_by_day=counts,
                resolution_rate=cluster["res"],
                avg_attention_score=cluster["attn"],
                avg_handle_time_seconds=cluster["dur"],
                share_by_day={
                    day: (n / day_totals[day] if day_totals.get(day) else 0.0)
                    for day, n in counts.items()
                },
            )
        )

    return TrendsResponse(
        baseline=TrendsBaseline(
            call_count=base["n"],
            resolution_rate=base["res"],
            avg_attention_score=base["attn"],
            avg_handle_time_seconds=base["dur"],
        ),
        issues=issues,
    )


@router.get(
    "/{cluster_id}/calls",
    response_model=list[CallSummary],
    responses={404: {"description": "No such cluster"}},
)
def cluster_calls(cluster_id: int, conn: DbConn, limit: int = 200):
    """The calls behind one issue. "179 appointment calls" is only useful if you
    can open them — this is the drill-through the trends view links to."""
    exists = conn.execute(
        "SELECT 1 FROM issue_clusters WHERE id = ?", (cluster_id,)
    ).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail=f"no such cluster: {cluster_id}")

    rows = conn.execute(
        """
        SELECT c.id, c.started_at, c.duration_seconds, c.intent_label,
               c.resolution_status, c.summary, c.attention_score,
               ROUND((SELECT AVG(verified) FROM evidence WHERE evidence.call_id = c.id) * 100, 1)
                   AS evidence_coverage
        FROM call_clusters cc
        JOIN calls c ON c.id = cc.call_id
        WHERE cc.cluster_id = ?
        ORDER BY c.attention_score DESC, c.started_at DESC
        LIMIT ?
        """,
        (cluster_id, limit),
    ).fetchall()
    return [CallSummary(**dict(r)) for r in rows]
