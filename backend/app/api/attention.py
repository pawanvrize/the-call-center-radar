"""GET /attention?date= — the ranked "needs a manager's attention today" view."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import DbConn
from app.schemas.call import CallSummary

router = APIRouter()


class AttentionDay(BaseModel):
    date: str
    call_count: int


class AttentionResponse(BaseModel):
    #: The day being shown. See `latest_call_date` for why this isn't "today".
    date: str | None
    #: Every day the corpus actually covers, so the UI can offer them.
    available_dates: list[AttentionDay]
    calls: list[CallSummary]
    #: % of every evidence row ever stored, corpus-wide, that passed
    #: verification. The single number behind "how much of what this system
    #: tells a manager can actually be traced back to a transcript" — the same
    #: query the eval harness runs (see schema.sql's comment on `evidence`),
    #: surfaced on the dashboard instead of buried in a test report.
    evidence_coverage_pct: float | None


def latest_call_date(conn) -> str | None:
    """What "today" means for this dataset.

    The corpus spans four days in 2020 (2020-03-15, 05-30, 06-01, 06-02), so a
    literal `DATE('now')` returns an empty list forever — the flagship view
    would be blank on stage. "Today" is therefore the most recent day that
    actually has calls, and the caller can override it with ?date=.
    """
    row = conn.execute("SELECT MAX(DATE(started_at)) AS d FROM calls").fetchone()
    return row["d"] if row and row["d"] else None


@router.get("", response_model=AttentionResponse)
def needs_attention(conn: DbConn, date: str | None = None, limit: int = 100):
    days = [
        AttentionDay(date=r["day"], call_count=r["n"])
        for r in conn.execute(
            """
            SELECT DATE(started_at) AS day, COUNT(*) AS n
            FROM calls GROUP BY day ORDER BY day DESC
            """
        )
    ]

    coverage_row = conn.execute("SELECT AVG(verified) AS coverage FROM evidence").fetchone()
    coverage_pct = (
        round(coverage_row["coverage"] * 100, 1)
        if coverage_row and coverage_row["coverage"] is not None
        else None
    )

    day = date or latest_call_date(conn)
    if day is None:
        return AttentionResponse(
            date=None, available_dates=days, calls=[], evidence_coverage_pct=coverage_pct
        )

    rows = conn.execute(
        """
        SELECT id, started_at, duration_seconds, intent_label,
               resolution_status, summary, attention_score
        FROM calls
        WHERE DATE(started_at) = ?
        -- SQLite sorts NULL below any value, so DESC puts unscored calls last:
        -- analysed calls rank above ones that haven't been.
        ORDER BY attention_score DESC, started_at DESC
        LIMIT ?
        """,
        (day, limit),
    ).fetchall()

    return AttentionResponse(
        date=day,
        available_dates=days,
        calls=[CallSummary(**dict(r)) for r in rows],
        evidence_coverage_pct=coverage_pct,
    )
