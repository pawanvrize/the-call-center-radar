#!/usr/bin/env python
"""Accuracy proof, not a claim.

Two numbers, deliberately of different cost:

**Citation pass rate** — fully automatic, needs no human labelling. Re-runs the
verifier over every stored citation and reports what fraction genuinely occur in
the cited turn AND support the claim. This is the number that speaks to the
brief's scoring rule, and almost no other team will have measured anything.

**Word error rate** — requires hand-checked references, so it is optional and
runs only over whatever gold transcripts exist. Ten carefully corrected calls
are worth more than thirty rushed ones.

Reporting the rejection rate honestly is the point. "We rejected 8% of generated
citations before they reached the screen" is a stronger claim than silence.

Usage:
    python scripts/eval_harness.py
    python scripts/eval_harness.py --gold-dir ../eval/gold_set
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_connection
from app.pipeline import verifier


def citation_report(conn) -> None:
    rows = conn.execute(
        """
        SELECT e.call_id, e.claim_type, e.claim_text, e.quote, e.verified,
               e.match_score, e.support_score, t.text AS turn_text
        FROM evidence e LEFT JOIN turns t ON t.id = e.turn_id
        """
    ).fetchall()

    if not rows:
        print("no citations stored — run scripts/analyze_dataset.py first")
        return

    print(f"\n{'=' * 62}\nCITATION VERIFICATION  ({len(rows)} citations)\n{'=' * 62}")

    # Re-verify from scratch rather than trusting the stored flag: this is the
    # harness, so it must not assume the thing it is measuring.
    recomputed = Counter()
    by_type: dict[str, Counter] = {}
    failures = []

    for row in rows:
        if not row["turn_text"]:
            recomputed["orphaned"] += 1
            continue
        result = verifier.verify_evidence(
            quote=row["quote"],
            turn_text=row["turn_text"],
            # Same per-type policy production uses, so this number matches what
            # the dashboard actually shows.
            claim=verifier.claim_for(row["claim_type"], row["claim_text"]),
        )
        bucket = by_type.setdefault(row["claim_type"], Counter())
        bucket["total"] += 1
        if result.verified:
            recomputed["pass"] += 1
            bucket["pass"] += 1
        else:
            recomputed["fail"] += 1
            failures.append((row["call_id"], row["claim_type"], result.reason))

    total = recomputed["pass"] + recomputed["fail"]
    if total:
        print(f"\n  overall pass rate : {recomputed['pass']}/{total} "
              f"= {recomputed['pass'] / total:.1%}")
    if recomputed["orphaned"]:
        print(f"  orphaned (no turn): {recomputed['orphaned']}")

    print("\n  by claim type:")
    for claim_type, counts in sorted(by_type.items()):
        rate = counts["pass"] / counts["total"] if counts["total"] else 0
        print(f"    {claim_type:20s} {counts['pass']:4d}/{counts['total']:<4d} {rate:6.1%}")

    if failures:
        print(f"\n  rejection reasons ({len(failures)} rejected):")
        for reason, n in Counter(f[2] for f in failures).most_common():
            print(f"    {n:4d}  {reason}")
        print("\n  worst offenders:")
        for call_id, claim_type, reason in failures[:5]:
            print(f"    {call_id}  {claim_type}: {reason}")

    stored_pass = sum(1 for r in rows if r["verified"])
    print(f"\n  stored-vs-recomputed: {stored_pass} stored verified, "
          f"{recomputed['pass']} on re-check")


def coverage_report(conn) -> None:
    """A claim with no evidence scores zero — so count claims lacking one."""
    print(f"\n{'=' * 62}\nCLAIM COVERAGE\n{'=' * 62}")
    row = conn.execute(
        """
        SELECT COUNT(*) AS analysed,
               SUM(CASE WHEN intent_label      IS NOT NULL THEN 1 ELSE 0 END) AS intents,
               SUM(CASE WHEN resolution_status IS NOT NULL THEN 1 ELSE 0 END) AS resolutions,
               SUM(CASE WHEN mood_shift_turn_id IS NOT NULL THEN 1 ELSE 0 END) AS shifts
        FROM calls WHERE analyzed_at IS NOT NULL
        """
    ).fetchone()

    if not row or not row["analysed"]:
        print("  no analysed calls")
        return

    n = row["analysed"]
    print(f"  analysed calls        : {n}")
    for name, key in (("with intent", "intents"), ("with resolution", "resolutions"),
                      ("with mood shift", "shifts")):
        print(f"  {name:22s}: {row[key]}/{n}")

    cited = conn.execute(
        """
        SELECT COUNT(DISTINCT call_id) AS n FROM evidence
        WHERE claim_type = 'intent' AND verified = 1
        """
    ).fetchone()["n"]
    print(f"  intents w/ VERIFIED cite: {cited}/{n}")


def wer_report(conn, gold_dir: Path) -> None:
    if not gold_dir or not gold_dir.is_dir():
        print(f"\n(no gold set at {gold_dir} — skipping WER)")
        return

    try:
        import jiwer
    except ImportError:
        print("\n(jiwer not installed — `pip install -r requirements-ml.txt` for WER)")
        return

    references = sorted(gold_dir.glob("*.txt"))
    if not references:
        print(f"\n(no *.txt reference transcripts in {gold_dir})")
        return

    print(f"\n{'=' * 62}\nWORD ERROR RATE  ({len(references)} gold transcripts)\n{'=' * 62}")
    scores = []
    for ref_path in references:
        call_id = ref_path.stem
        rows = conn.execute(
            "SELECT text FROM turns WHERE call_id = ? ORDER BY turn_index", (call_id,)
        ).fetchall()
        if not rows:
            print(f"  {call_id}: not in database, skipped")
            continue
        hypothesis = " ".join(r["text"] for r in rows)
        reference = ref_path.read_text(encoding="utf-8")
        wer = jiwer.wer(reference.lower(), hypothesis.lower())
        scores.append(wer)
        print(f"  {call_id}: WER {wer:.1%}")

    if scores:
        print(f"\n  mean WER: {sum(scores) / len(scores):.1%}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-dir", type=Path,
                        default=Path(__file__).resolve().parent.parent.parent / "eval" / "gold_set")
    args = parser.parse_args()

    conn = get_connection()
    citation_report(conn)
    coverage_report(conn)
    wer_report(conn, args.gold_dir)
    conn.close()
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
