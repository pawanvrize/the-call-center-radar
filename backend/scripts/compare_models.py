#!/usr/bin/env python
"""A/B two reasoning models on the metric that actually matters here.

Not a benchmark score — the citation pass rate on this corpus, which is what
the brief grades. Reads only; nothing is written to the database, so this is
safe to run against a finished dataset.

    python scripts/compare_models.py --limit 40 \
        --models openai.gpt-oss-120b-1:0 us.anthropic.claude-haiku-4-5-20251001-v1:0
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db.session import get_connection
from app.pipeline import reasoning, verifier
from app.pipeline.analyze import load_turns


def score_call(call_id: str, model: str) -> dict | None:
    """Run one call through one model and verify the citations it produces."""
    conn = get_connection()
    try:
        stored = load_turns(conn, call_id)
        if not stored:
            return None
        turns = [s.turn for s in stored]

        original = settings.bedrock_model
        try:
            settings.bedrock_model = model
            result = reasoning.analyze_call(turns)
        finally:
            settings.bedrock_model = original

        out = {"intent_ok": 0, "resolution_ok": 0, "n": 1,
               "summary_words": len(result.summary.split())}

        for kind, claim, idx in (
            ("intent", result.intent.label, result.intent.turn_index),
            ("resolution",
             f"the customer wanted to {result.intent.label}; "
             f"this was {result.resolution.label}",
             result.resolution.turn_index),
        ):
            if not (0 <= idx < len(stored)):
                continue
            turn = stored[idx].turn
            quote = verifier.select_quote(turn.text, claim)
            check = verifier.verify_evidence(
                quote=quote, turn_text=turn.text,
                claim=verifier.claim_for(kind, claim),
            )
            if check.verified:
                out[f"{kind}_ok"] = 1
        return out
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:70]}"}
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--models", nargs="+", required=True)
    args = parser.parse_args()

    conn = get_connection()
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM calls WHERE analyzed_at IS NOT NULL ORDER BY id LIMIT ?",
        (args.limit,))]
    conn.close()

    print(f"comparing {len(args.models)} models over the same {len(ids)} calls\n")
    rows = []

    for model in args.models:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = [r for r in pool.map(lambda c: score_call(c, model), ids) if r]

        errors = [r for r in results if "error" in r]
        ok = [r for r in results if "error" not in r]
        n = len(ok) or 1
        row = {
            "model": model,
            "intent": sum(r["intent_ok"] for r in ok) / n,
            "resolution": sum(r["resolution_ok"] for r in ok) / n,
            "words": sum(r["summary_words"] for r in ok) / n,
            "errors": len(errors),
        }
        row["overall"] = (row["intent"] + row["resolution"]) / 2
        rows.append(row)
        if errors:
            print(f"  {model}: {len(errors)} errors, e.g. {errors[0]['error']}")

    width = max(len(r["model"]) for r in rows)
    print(f"\n{'model':<{width}}  {'intent':>7} {'resoln':>7} {'overall':>8} "
          f"{'summary':>8} {'errors':>7}")
    print("-" * (width + 42))
    for r in sorted(rows, key=lambda x: -x["overall"]):
        print(f"{r['model']:<{width}}  {r['intent']:6.1%} {r['resolution']:6.1%} "
              f"{r['overall']:7.1%} {r['words']:7.0f}w {r['errors']:7d}")

    best, worst = rows[0], rows[-1]
    gap = abs(best["overall"] - worst["overall"])
    print(f"\nspread between best and worst: {gap:.1%}")
    if gap < 0.03:
        print("=> within noise at this sample size. The bottleneck is the data,\n"
              "   not the model — pick on cost, latency and availability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
