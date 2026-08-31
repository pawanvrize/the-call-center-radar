#!/usr/bin/env python
"""Stages 4-6 over every transcribed call: mood, reasoning, verification,
attention score, then a final cross-call clustering pass.

Separate from ingest_dataset.py on purpose. Transcription is slow, expensive and
done once; analysis is fast, free and re-run constantly while prompts and
weights are tuned. Keeping them apart means iterating on the intelligence layer
never touches the audio.

Usage:
    python scripts/analyze_dataset.py --workers 8      # everything unanalysed
    python scripts/analyze_dataset.py --limit 20
    python scripts/analyze_dataset.py --reanalyze      # redo already-analysed
    python scripts/analyze_dataset.py --cluster-only   # just redo trends
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_connection, init_db
from app.pipeline import clustering
from app.pipeline.analyze import (
    persist_analysis,
    prepare_analysis,
    recompute_attention,
)


def median_handle_time(conn) -> float:
    rows = [r["duration_seconds"] for r in
            conn.execute("SELECT duration_seconds FROM calls ORDER BY duration_seconds")]
    if not rows:
        return 0.0
    mid = len(rows) // 2
    return rows[mid] if len(rows) % 2 else (rows[mid - 1] + rows[mid]) / 2


def run_clustering(conn) -> None:
    """Cross-call pass: cluster analysed calls into emergent issue groups."""
    rows = conn.execute(
        """
        SELECT id, COALESCE(intent_label, '') || '. ' || COALESCE(summary, '') AS text
        FROM calls WHERE analyzed_at IS NOT NULL
        """
    ).fetchall()

    if not rows:
        print("clustering: no analysed calls yet")
        return

    result = clustering.cluster_calls([r["text"] for r in rows])
    n_clusters = len({label for label in result.labels if label != -1})

    with conn:
        conn.execute("DELETE FROM call_clusters")
        conn.execute("DELETE FROM issue_clusters")

        db_ids: dict[int, int] = {}
        for label, name in result.names.items():
            cursor = conn.execute(
                "INSERT INTO issue_clusters (label, created_at) VALUES (?, datetime('now'))",
                (name,),
            )
            db_ids[label] = cursor.lastrowid

        conn.executemany(
            "INSERT INTO call_clusters (call_id, cluster_id) VALUES (?, ?)",
            [(row["id"], db_ids[label])
             for row, label in zip(rows, result.labels) if label != -1],
        )

    print(f"\nclustering: {n_clusters} clusters over {len(rows)} calls "
          f"({result.noise_ratio:.0%} noise)")
    if result.noise_ratio > 0.3:
        print("  note: >30% noise — consider FASTopic, which handles short texts "
              "better than HDBSCAN over embeddings")
    for label, name in sorted(result.names.items())[:12]:
        n = sum(1 for x in result.labels if x == label)
        print(f"    {n:4d}  {name}")


def _rescore(conn) -> None:
    """Re-score attention now that clusters exist.

    Repeat-contact detection asks "has this customer called about THIS issue
    before", which needs the issue clusters — and those can only be built after
    every call has a summary. Hence: analyse, cluster, then re-score. No LLM
    calls, so it's seconds rather than minutes.
    """
    stats = recompute_attention(conn, median_handle_time(conn))
    print(
        f"\nattention re-scored with issue-aware repeat contact: "
        f"{stats['rescored']} calls, {stats['with_repeat_contact']} flagged as "
        f"a repeat contact on the same issue"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--call-id", default=None)
    parser.add_argument("--reanalyze", action="store_true",
                        help="re-run calls that already have analysis")
    parser.add_argument("--cluster-only", action="store_true",
                        help="skip per-call analysis, just rebuild trends")
    parser.add_argument("--skip-cluster", action="store_true")
    parser.add_argument("--workers", type=int, default=8,
                        help="parallel workers. The LLM call is network-bound, so "
                             "this is a large win; keep at or under the provider's "
                             "requests-per-minute limit.")
    args = parser.parse_args()

    init_db()
    conn = get_connection()

    if args.cluster_only:
        run_clustering(conn)
        _rescore(conn)
        conn.close()
        return 0

    where = "transcribed_at IS NOT NULL"
    if not args.reanalyze:
        where += " AND analyzed_at IS NULL"
    params: tuple = ()
    if args.call_id:
        where += " AND id = ?"
        params = (args.call_id,)

    sql = f"SELECT id FROM calls WHERE {where} ORDER BY id"
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"

    call_ids = [r["id"] for r in conn.execute(sql, params)]
    if not call_ids:
        print("nothing to analyse — transcribe some calls first")
        return 0

    median = median_handle_time(conn)
    print(f"analysing {len(call_ids)} calls  (median handle time {median:.0f}s, "
          f"workers={args.workers})")

    done = failed = citations = verified = 0
    started = time.monotonic()

    def work(call_id: str):
        """Worker thread: reads + LLM call + verification, but never writes.

        Its own connection — SQLite connections are not shareable across
        threads — and no open write transaction, so the ~10s network call
        never blocks another worker's commit.
        """
        thread_conn = get_connection()
        try:
            return prepare_analysis(thread_conn, call_id, median)
        finally:
            thread_conn.close()

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(work, cid): cid for cid in call_ids}
        for i, future in enumerate(as_completed(futures), 1):
            call_id = futures[future]
            try:
                summary = persist_analysis(conn, future.result())
                done += 1
                citations += summary["citations"]
                verified += summary["verified"]
                if i % 25 == 0 or i == len(call_ids):
                    rate = i / max(time.monotonic() - started, 1e-6)
                    left = (len(call_ids) - i) / rate if rate else 0
                    pass_rate = verified / citations if citations else 0
                    print(f"[{i}/{len(call_ids)}] {done} ok, {failed} failed "
                          f"— {rate * 60:.0f}/min, ~{left / 60:.0f} min left, "
                          f"citations {pass_rate:.0%}")
            except Exception as e:
                failed += 1
                print(f"[{i}/{len(call_ids)}] {call_id}  FAILED: "
                      f"{type(e).__name__}: {str(e)[:120]}")

    total = time.monotonic() - started
    print(f"\nanalysed={done} failed={failed} in {total:.1f}s")
    if citations:
        print(f"citation pass rate: {verified}/{citations} = {verified / citations:.1%}")

    if not args.skip_cluster and done:
        run_clustering(conn)
        # Repeat-contact detection needs clusters, which only exist now. Cheap
        # (no LLM), so re-score every call rather than leaving the factor cold.
        _rescore(conn)

    conn.close()
    return 1 if failed and not done else 0


if __name__ == "__main__":
    raise SystemExit(main())
