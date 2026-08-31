"""GET /calls/{id} — the full grounded detail: transcript, intent, mood timeline,
resolution, summary, needs-attention score, all with evidence.

Evidence is joined from the `evidence` table rather than read out of JSON blobs,
so a claim whose citation failed verification arrives at the UI flagged as
unverified instead of being quietly presented as fact.
"""
import json

from fastapi import APIRouter, HTTPException

from app.db.session import DbConn
from app.schemas.call import (
    AttentionFactor,
    CallDetail,
    Evidence,
    ResolutionContradiction,
    Turn,
    Word,
)

router = APIRouter()


def _evidence_by_type(conn, call_id: str) -> dict[str, list[Evidence]]:
    rows = conn.execute(
        """
        SELECT claim_type, turn_id, timestamp, quote, verified
        FROM evidence WHERE call_id = ? ORDER BY id
        """,
        (call_id,),
    ).fetchall()

    grouped: dict[str, list[Evidence]] = {}
    for r in rows:
        grouped.setdefault(r["claim_type"], []).append(
            Evidence(
                turn_id=r["turn_id"] or 0,
                timestamp=r["timestamp"],
                quote=r["quote"],
                verified=bool(r["verified"]),
            )
        )
    return grouped


@router.get(
    "/{call_id}",
    response_model=CallDetail,
    responses={404: {"description": "No such call"}},
)
def get_call(call_id: str, conn: DbConn):
    call = conn.execute(
        """
        SELECT calls.*, customers.name AS customer_name, agents.name AS agent_name
        FROM calls
        JOIN customers ON customers.id = calls.customer_id
        JOIN agents    ON agents.id    = calls.agent_id
        WHERE calls.id = ?
        """,
        (call_id,),
    ).fetchone()
    if not call:
        raise HTTPException(status_code=404, detail=f"no such call: {call_id}")

    turn_rows = conn.execute(
        """
        SELECT id, turn_index, speaker, start_seconds, end_seconds,
               text, words_json, mood_score, overlapping
        FROM turns WHERE call_id = ? ORDER BY turn_index
        """,
        (call_id,),
    ).fetchall()

    turns = [
        Turn(
            id=r["id"],
            turn_index=r["turn_index"],
            speaker=r["speaker"],
            start_seconds=r["start_seconds"],
            end_seconds=r["end_seconds"],
            text=r["text"],
            words=[Word(**w) for w in json.loads(r["words_json"] or "[]")],
            mood_score=r["mood_score"],
            overlapping=bool(r["overlapping"]),
        )
        for r in turn_rows
    ]

    ev = _evidence_by_type(conn, call_id)
    first = lambda kind: (ev.get(kind) or [None])[0]

    resolution_contradiction = None
    agent_ev, customer_ev = first("resolution_contradiction_agent"), first(
        "resolution_contradiction_customer"
    )
    if agent_ev and customer_ev:
        resolution_contradiction = ResolutionContradiction(
            agent_evidence=agent_ev, customer_evidence=customer_ev
        )

    coverage_row = conn.execute(
        "SELECT AVG(verified) AS coverage FROM evidence WHERE call_id = ?", (call_id,)
    ).fetchone()
    evidence_coverage = (
        round(coverage_row["coverage"] * 100, 1)
        if coverage_row and coverage_row["coverage"] is not None
        else None
    )

    factors = []
    for f in json.loads(call["attention_factors_json"] or "[]"):
        factors.append(
            AttentionFactor(
                factor=f["factor"],
                weight=f["weight"],
                evidence=Evidence(**f["evidence"]) if f.get("evidence") else None,
            )
        )

    return CallDetail(
        id=call["id"],
        customer_id=call["customer_id"],
        customer_name=call["customer_name"],
        agent_id=call["agent_id"],
        agent_name=call["agent_name"],
        started_at=call["started_at"],
        duration_seconds=call["duration_seconds"],
        # Served through the API's own /audio mount, which the Next.js rewrite
        # proxies — keeps playback same-origin so Range requests just work.
        audio_url=f"/audio/{call['audio_path']}",
        transcript_provider=call["transcript_provider"],
        turns=turns,
        intent_label=call["intent_label"],
        intent_evidence=first("intent"),
        resolution_status=call["resolution_status"],
        resolution_evidence=first("resolution"),
        summary=call["summary"],
        mood_shift_turn_id=call["mood_shift_turn_id"],
        mood_shift_evidence=first("mood_shift"),
        attention_score=call["attention_score"],
        attention_factors=factors,
        resolution_contradiction=resolution_contradiction,
        evidence_coverage=evidence_coverage,
    )
