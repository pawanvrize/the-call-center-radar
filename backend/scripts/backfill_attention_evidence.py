#!/usr/bin/env python
"""Re-cite the attention factors on already-analysed calls. No LLM calls.

Why this exists rather than just re-running analyze_dataset.py: that script
re-asks the model for intent, resolution and summary on every call, which costs
real money and ~90 minutes to reproduce judgments that have not changed. The
only thing that changed is which turn each attention factor points at, and every
input needed for that is already in SQLite — the mood scores on `turns`, the
resolution turn in `evidence`, the detected shift on `calls`.

So this reads what is there, recomputes the factors with their citations, and
writes back. Intent, resolution and summary are never touched.

Usage:
    python scripts/backfill_attention_evidence.py --db ../data/radar.db [--limit N] [--dry-run]
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import attention_score, changepoint, mood
from app.pipeline.analyze import (
    _build_evidence,
    is_citable_shift,
    load_turns,
)


def median_handle_time(conn: sqlite3.Connection) -> float:
    rows = [
        r[0]
        for r in conn.execute(
            "SELECT duration_seconds FROM calls WHERE duration_seconds IS NOT NULL"
            " ORDER BY duration_seconds"
        )
    ]
    return rows[len(rows) // 2] if rows else 0.0


def prior_same_issue_count(conn: sqlite3.Connection, call_id: str, intent_label: str) -> int:
    """Mirror of analyze.prior_same_issue_count — same issue, not any prior call."""
    if not intent_label:
        return 0
    row = conn.execute(
        """
        SELECT COUNT(*) FROM calls
        WHERE customer_id = (SELECT customer_id FROM calls WHERE id = ?)
          AND started_at < (SELECT started_at FROM calls WHERE id = ?)
          AND intent_label = ?
        """,
        (call_id, call_id, intent_label),
    ).fetchone()
    return row[0] if row else 0


def turn_index_of(stored, db_id):
    if db_id is None:
        return None
    for i, s in enumerate(stored):
        if s.db_id == db_id:
            return i
    return None


def recite_one(conn: sqlite3.Connection, call: sqlite3.Row, median: float) -> dict:
    call_id = call["id"]
    stored = load_turns(conn, call_id)
    if not stored:
        return {"skipped": True}

    turns = [s.turn for s in stored]

    # --- recover the turn indices the factors need to cite -------------------
    # Resolution: whichever turn the stored resolution citation already points
    # at. Reusing it keeps the factor and the judgment pointing at one moment.
    res_row = conn.execute(
        "SELECT turn_id FROM evidence WHERE call_id = ? AND claim_type = 'resolution'",
        (call_id,),
    ).fetchone()
    resolution_turn_index = turn_index_of(stored, res_row["turn_id"] if res_row else None)

    # Mood is RECOMPUTED, not read back. The stored scores predate the
    # MIN_MOOD_WORDS floor, so reusing them would carry the noise this change
    # exists to remove. Recomputing is cheap — VADER plus word timings, no
    # audio decode and no network — which is the whole reason the LLM stages
    # can be skipped while this one is redone.
    points = mood.score_customer_turns(turns)
    mood_updates = [(p.score, stored[p.turn_index].db_id) for p in points]

    worst_point = min(points, key=lambda p: p.score, default=None)
    worst_mood = worst_point.score if worst_point else None
    worst_mood_turn_index = (
        worst_point.turn_index
        if worst_point and is_citable_shift(stored[worst_point.turn_index].turn)
        else None
    )

    # The change point moves with the series it is computed from, so it is
    # re-derived too rather than trusted from the old run.
    shift = changepoint.find_mood_shift(
        [p.score for p in points], [p.turn_index for p in points]
    )
    if shift is not None and not is_citable_shift(stored[shift.turn_index].turn):
        shift = None
    shift_turn_index = shift.turn_index if shift else None
    mood_shift_delta = shift.delta if shift else None

    # Rebuild the shift's own citation from the recomputed shift. Always, not
    # only when it moved: leaving the previous run's quote in place would mean
    # the dashboard cites one turn for a shift now detected at another.
    shift_row = None
    if shift is not None:
        direction = "worse" if shift.delta < 0 else "better"
        shift_row = _build_evidence(
            "mood_shift",
            f"the customer's mood turned {direction} at this point in the call",
            stored,
            shift.turn_index,
            check_support=False,  # our detector chose the turn; the quote is a pointer
        )

    intent_row = conn.execute(
        "SELECT turn_id FROM evidence WHERE call_id = ? AND claim_type = 'intent'",
        (call_id,),
    ).fetchone()
    intent_turn_index = turn_index_of(stored, intent_row["turn_id"] if intent_row else None)

    repeat_count = prior_same_issue_count(conn, call_id, call["intent_label"])
    result = attention_score.compute_attention_score(
        resolution_status=call["resolution_status"],
        worst_mood=worst_mood,
        mood_shift_delta=mood_shift_delta,
        escalation_hits=mood.escalation_hits(turns),
        handle_time_seconds=call["duration_seconds"] or 0.0,
        median_handle_time_seconds=median,
        is_repeat_contact=repeat_count > 0,
        repeat_count=repeat_count,
        resolution_turn_index=resolution_turn_index,
        worst_mood_turn_index=worst_mood_turn_index,
        mood_shift_turn_index=shift_turn_index,
        intent_turn_index=intent_turn_index,
    )

    # --- build the citations -------------------------------------------------
    # Only citations this script does not rebuild are reusable — intent and
    # resolution. The mood-shift row is regenerated above.
    existing = {
        r["turn_id"]: r
        for r in conn.execute(
            "SELECT turn_id, timestamp, quote, verified FROM evidence"
            " WHERE call_id = ? AND claim_type IN ('intent', 'resolution')",
            (call_id,),
        )
    }
    if shift_row is not None:
        existing[shift_row.turn_db_id] = {
            "turn_id": shift_row.turn_db_id,
            "timestamp": shift_row.timestamp,
            "quote": shift_row.quote,
            "verified": shift_row.verified,
        }

    new_rows, factors_json, cited = [], [], 0
    if shift_row is not None:
        new_rows.append(shift_row)
    for factor in result.factors:
        payload = None
        if factor.turn_index is not None and 0 <= factor.turn_index < len(stored):
            db_id = stored[factor.turn_index].db_id
            if db_id in existing:  # reuse a citation that already exists
                e = existing[db_id]
                payload = {
                    "turn_id": db_id,
                    "timestamp": e["timestamp"],
                    "quote": e["quote"],
                    "verified": bool(e["verified"]),
                }
            else:
                row = _build_evidence(
                    "attention_factor",
                    factor.factor,
                    stored,
                    factor.turn_index,
                    check_support=factor.check_support,
                )
                if row:
                    new_rows.append(row)
                    payload = {
                        "turn_id": row.turn_db_id,
                        "timestamp": row.timestamp,
                        "quote": row.quote,
                        "verified": row.verified,
                    }
        cited += payload is not None
        factors_json.append(
            {"factor": factor.factor, "weight": factor.weight, "evidence": payload}
        )

    return {
        "call_id": call_id,
        "score": result.score,
        "prev_score": call["attention_score"],
        "factors": len(result.factors),
        "cited": cited,
        "factors_json": json.dumps(factors_json),
        "new_rows": new_rows,
        "mood_updates": mood_updates,
        # Turns that no longer clear the floor must be cleared, not left holding
        # a stale score from the previous run.
        "clear_ids": [
            s.db_id
            for s in stored
            if s.db_id not in {db_id for _, db_id in mood_updates}
        ],
        "shift_db_id": stored[shift_turn_index].db_id if shift_turn_index is not None else None,
        "prev_shift_db_id": call["mood_shift_turn_id"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")

    median = median_handle_time(conn)
    sql = "SELECT * FROM calls WHERE analyzed_at IS NOT NULL ORDER BY id"
    if args.limit:
        sql += f" LIMIT {args.limit}"
    calls = conn.execute(sql).fetchall()

    tot_f = tot_c = changed = 0
    for n, call in enumerate(calls, 1):
        out = recite_one(conn, call, median)
        if out.get("skipped"):
            continue
        tot_f += out["factors"]
        tot_c += out["cited"]
        changed += out["score"] != out["prev_score"]

        if not args.dry_run:
            with conn:
                conn.executemany(
                    "UPDATE turns SET mood_score = ? WHERE id = ?", out["mood_updates"]
                )
                conn.executemany(
                    "UPDATE turns SET mood_score = NULL WHERE id = ?",
                    [(i,) for i in out["clear_ids"]],
                )
                # Both are rebuilt from the recomputed series every run, so
                # clear them unconditionally — a stale mood-shift quote for a
                # shift no longer claimed is exactly the unsupported evidence
                # the brief penalises.
                conn.execute(
                    "DELETE FROM evidence WHERE call_id = ?"
                    " AND claim_type IN ('attention_factor', 'mood_shift')",
                    (out["call_id"],),
                )
                conn.execute(
                    "UPDATE calls SET mood_shift_turn_id = ? WHERE id = ?",
                    (out["shift_db_id"], out["call_id"]),
                )
                conn.executemany(
                    """INSERT INTO evidence (call_id, claim_type, claim_text, turn_id,
                                             timestamp, quote, match_score, support_score, verified)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    [
                        (out["call_id"], r.claim_type, r.claim_text, r.turn_db_id,
                         r.timestamp, r.quote, r.match_score, r.support_score, r.verified)
                        for r in out["new_rows"]
                    ],
                )
                conn.execute(
                    "UPDATE calls SET attention_score = ?, attention_factors_json = ? WHERE id = ?",
                    (out["score"], out["factors_json"], out["call_id"]),
                )

        if n % 200 == 0:
            print(f"  {n}/{len(calls)} … {tot_c}/{tot_f} factors cited", flush=True)

    print()
    print(f"calls processed : {len(calls)}")
    print(f"factors         : {tot_f}")
    print(f"factors cited   : {tot_c} ({100 * tot_c / max(tot_f, 1):.1f}%)")
    print(f"scores changed  : {changed}")
    if args.dry_run:
        print("\n(dry run — nothing written)")


if __name__ == "__main__":
    main()
