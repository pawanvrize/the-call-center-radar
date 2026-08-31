#!/usr/bin/env python
"""Detect and correct calls where the source recording has agent and customer
on the OPPOSITE channels from the brief's stated convention.

The whole pipeline trusts channel identity absolutely: left is the agent,
right is the customer, by construction, no diarization involved. That is a
real strength — it's zero-error by design for every call where it holds. But
"by construction" is only as good as the assumption underneath it, and it
does not universally hold on this corpus.

Found by manually inspecting flagged calls after a user reported agent/customer
looking backwards on some names they'd spot-checked. Measured directly: 35 of
1,441 calls (2.4%) have the agent's own scripted opening line — "Hello, this is
Harper Valley National Bank. My name is X. How can I help you today?", spoken
by every agent in every call — appearing on the channel this pipeline had
labelled 'customer'. Manually verified against full transcripts: these are not
isolated misheard turns, they are whole-call swaps, consistent from the first
turn to the last.

Two broader heuristics were tried and rejected before this one:

  - Matching only a customer's or agent's FIRST name against early turns.
    Produced 158 "matches" that were overwhelmingly false positives — with
    only 10 distinct agent first names shared across 100 customers, name
    coincidences ("my name is also Michael") are common and look identical to
    a swap under first-name matching alone.
  - Matching a customer's FULL name anywhere in an agent-labelled turn. Better,
    but still false-positives on the very normal case of an agent repeating a
    customer's name back to them mid-call ("Let me check that for you, Linda
    Smith") — which is completely correct labelling, not a swap.

What actually works: the agent's opening line is scripted and deterministic —
every real agent turn 0 says it, verbatim modulo ASR noise. A single strict,
typo-tolerant match against turn 0 specifically (not "any of the first few
turns", which reintroduces the same false-positive modes above) has no
plausible innocent explanation if it lands on the labelled-customer channel.

Usage:
    python scripts/fix_channel_swaps.py --dry-run     # report only
    python scripts/fix_channel_swaps.py               # fix + re-analyse
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_connection  # noqa: E402
from app.pipeline.analyze import persist_analysis, prepare_analysis  # noqa: E402

#: Tolerant of the ASR variants actually observed: Harper/Harbor/Hapa/Harford/
#: Upper Valley, and stutter-repeats ("Hello, this is Harper— hello, this is
#: Harper Valley..."). Requires the deterministic shape — greeting, bank name,
#: self-intro — not just any one fragment of it, which is what keeps this
#: specific compared to the broader, false-positive-prone checks above.
GREETING_SCRIPT = re.compile(
    r"(hello|hi)[,.]?\s*(this is|hello,? this is).{0,25}(valley|national)\s*"
    r"(national\s*)?bank\.?\s*my name is \w+",
    re.IGNORECASE,
)


def find_swapped_calls(conn) -> list[str]:
    rows = conn.execute(
        "SELECT call_id, text FROM turns WHERE turn_index = 0 AND speaker = 'customer'"
    ).fetchall()
    return sorted({r["call_id"] for r in rows if GREETING_SCRIPT.search(r["text"])})


def median_handle_time(conn) -> float:
    rows = [r[0] for r in conn.execute(
        "SELECT duration_seconds FROM calls ORDER BY duration_seconds"
    )]
    return rows[len(rows) // 2] if rows else 0.0


def flip_speakers(conn, call_id: str) -> None:
    with conn:
        conn.execute(
            """UPDATE turns SET speaker = CASE speaker
               WHEN 'agent' THEN 'customer' ELSE 'agent' END
               WHERE call_id = ?""",
            (call_id,),
        )
        # Every downstream judgment depends on which channel is the customer —
        # clear it all rather than leave stale analysis sitting under a now-
        # corrected transcript.
        conn.execute(
            """UPDATE calls SET intent_label=NULL, resolution_status=NULL,
               summary=NULL, mood_shift_turn_id=NULL, attention_score=NULL,
               attention_factors_json=NULL, analyzed_at=NULL WHERE id=?""",
            (call_id,),
        )
        conn.execute("DELETE FROM evidence WHERE call_id=?", (call_id,))
        conn.execute("DELETE FROM call_clusters WHERE call_id=?", (call_id,))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_connection()
    swapped = find_swapped_calls(conn)

    print(f"calls with the agent's script on the customer channel: "
          f"{len(swapped)} / {conn.execute('SELECT COUNT(*) FROM calls').fetchone()[0]}")
    for cid in swapped:
        print(" ", cid)

    if args.dry_run or not swapped:
        conn.close()
        return 0

    print("\nflipping speaker labels and clearing stale analysis...")
    for cid in swapped:
        flip_speakers(conn, cid)

    print("re-analysing with corrected transcripts (LLM calls, ~3s/call)...")
    median = median_handle_time(conn)
    ok = failed = 0
    t0 = time.monotonic()
    for i, cid in enumerate(swapped, 1):
        try:
            persist_analysis(conn, prepare_analysis(conn, cid, median))
            ok += 1
        except Exception as e:
            failed += 1
            print(f"  FAILED {cid}: {type(e).__name__}: {str(e)[:150]}")
        if i % 10 == 0 or i == len(swapped):
            print(f"  [{i}/{len(swapped)}] ok={ok} failed={failed} "
                  f"({time.monotonic() - t0:.0f}s)")

    print(f"\ndone: {ok} re-analysed, {failed} failed.")
    print("Run `python scripts/analyze_dataset.py --cluster-only` next — these "
          "calls' summaries changed, so clustering and repeat-contact "
          "detection need a fresh pass over the whole corpus to stay consistent.")

    conn.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
