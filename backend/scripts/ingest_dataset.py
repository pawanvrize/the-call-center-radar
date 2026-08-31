#!/usr/bin/env python
"""Run the pipeline over the dataset once, caching results in SQLite.

"Do not re-transcribe on every request" — this script is the only place bulk
transcription happens; the API and dashboard only ever read the result.
Re-running is safe and cheap: calls already transcribed are skipped, and even a
forced re-run reads from the on-disk transcript cache rather than re-spending
API credit.

Usage:
    python scripts/ingest_dataset.py                     # everything
    python scripts/ingest_dataset.py --limit 20          # throughput test
    python scripts/ingest_dataset.py --call-id <sid>     # one specific call
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import store
from app.db.session import get_connection, init_db
from app.pipeline import run_batch
from app.pipeline.metadata import iter_metadata, parse_metadata
from app.pipeline.transcribe import get_transcriber


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(settings.data_dir),
                        help="directory containing audio/ and metadata/")
    parser.add_argument("--limit", type=int, default=None,
                        help="process only the first N calls (throughput test)")
    parser.add_argument("--call-id", default=None,
                        help="process a single call by id")
    parser.add_argument("--provider", default=None,
                        help="override TRANSCRIBER_PROVIDER for this run")
    parser.add_argument("--reprocess", action="store_true",
                        help="re-run turn merging and storage from CACHED transcripts "
                             "(cheap — no re-transcription, no API spend)")
    parser.add_argument("--force", action="store_true",
                        help="ignore the transcript cache and re-transcribe "
                             "(expensive — re-spends API credit)")
    parser.add_argument("--workers", type=int, default=1,
                        help="parallel transcription workers. AssemblyAI is "
                             "network-bound so 8-12 is a large win; for local "
                             "whisper keep it near your core count.")
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    if not (data_dir / "metadata").is_dir():
        print(f"error: {data_dir}/metadata not found — is the dataset unzipped?")
        return 1

    init_db()
    cache_dir, work_dir = store.init_data_dirs(data_dir)
    transcriber = get_transcriber(args.provider)
    conn = get_connection()

    if args.call_id:
        metas = [parse_metadata(data_dir / "metadata" / f"{args.call_id}.json")]
    else:
        metas = list(iter_metadata(data_dir, limit=args.limit))

    print(f"provider={transcriber.name}  calls={len(metas)}  cache={cache_dir}")

    pending = []
    skipped = 0
    for meta in metas:
        if store.is_transcribed(conn, meta.call_id, transcriber.name) and not (
            args.force or args.reprocess
        ):
            skipped += 1
            continue
        pending.append(meta)

    print(f"pending={len(pending)} skipped={skipped} workers={args.workers}")

    done = failed = 0
    started = time.monotonic()

    def work(meta):
        """Runs on a worker thread — transcription only, never the database."""
        turns = run_batch.transcribe_call(
            meta,
            run_batch.audio_path_for(data_dir, meta.call_id),
            cache_dir, work_dir, transcriber, force=args.force,
        )
        return meta, turns

    # Transcription fans out across threads; every SQLite write happens here on
    # the main thread. That sidesteps SQLite's threading rules entirely rather
    # than trying to satisfy them under concurrency.
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(work, meta): meta for meta in pending}
        for i, future in enumerate(as_completed(futures), 1):
            meta = futures[future]
            try:
                meta, turns = future.result()
                run_batch.store_transcript(conn, meta, turns, transcriber.name)
                done += 1
                if i % 25 == 0 or i == len(pending):
                    rate = i / max(time.monotonic() - started, 1e-6)
                    remaining = (len(pending) - i) / rate if rate else 0
                    print(f"[{i}/{len(pending)}] {done} ok, {failed} failed "
                          f"— {rate * 60:.0f}/min, ~{remaining / 60:.0f} min left")
            except Exception as e:  # one bad call must not kill the batch
                failed += 1
                print(f"[{i}/{len(pending)}] {meta.call_id}  FAILED: "
                      f"{type(e).__name__}: {str(e)[:120]}")

    total = time.monotonic() - started
    print(
        f"\ntranscribed={done} skipped={skipped} failed={failed} in {total:.1f}s"
        + (f"  ({total / done:.2f}s per call)" if done else "")
    )
    conn.close()
    return 1 if failed and not done else 0


if __name__ == "__main__":
    raise SystemExit(main())
