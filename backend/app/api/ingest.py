"""POST /ingest — the live path for a recording that was never in the batch.

This is the same code the overnight batch runs: split -> transcribe -> merge ->
mood -> reasoning -> verified citations -> attention score. Not a demo-only
happy path, which is the point — if this works on a recording nobody has seen,
the precomputed 1,441 aren't a lookup table.

Synchronous from the caller's perspective by design. Calls in this corpus
average 58 seconds and the whole pipeline takes ~10s wall clock, so one
request/response is simpler and more convincing on stage than a job id the
audience has to watch you poll.

Threading note: the upload is read on the event loop (async), but every SQLite
and pipeline call runs inside `run_in_threadpool`. Two reasons — SQLite
connections cannot cross threads, and the pipeline blocks for seconds at a
time, which would stall every other request if it ran on the loop.
"""
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db.session import get_connection
from app.pipeline import analyze, run_batch
from app.pipeline.metadata import CallMetadata, slugify

router = APIRouter()

#: Uploads above this are refused rather than silently tying up a worker.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post(
    "",
    responses={
        400: {"description": "Unusable audio (not stereo, empty, or too large)"},
        502: {"description": "Transcription or reasoning provider failed"},
    },
)
async def ingest_call(
    audio: UploadFile = File(..., description="Stereo recording; left=agent, right=customer"),
    customer_name: str = Form(...),
    agent_name: str = Form(...),
    started_at: str | None = Form(None, description="ISO 8601; defaults to now"),
):
    """Transcribe and analyse one new recording, then return its full detail."""
    data_dir = Path(settings.data_dir)
    call_id = uuid.uuid4().hex[:16]
    audio_path = data_dir / "audio" / f"{call_id}.mp3"
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    # Streamed to disk rather than held in memory — the file also has to live
    # here permanently for the dashboard's audio player to serve it.
    size = 0
    try:
        with audio_path.open("wb") as out:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=f"upload exceeds {MAX_UPLOAD_BYTES // 1024 // 1024}MB",
                    )
                # Blocking disk I/O, off the event loop — see module docstring;
                # this call was the one place that contradicted it, stalling
                # every other in-flight request for as long as the write took.
                await run_in_threadpool(out.write, chunk)
    except HTTPException:
        audio_path.unlink(missing_ok=True)
        raise

    if size == 0:
        audio_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    # subprocess.run() blocks synchronously; off the event loop for the same
    # reason as the write above.
    duration, channels = await run_in_threadpool(_probe, audio_path)
    if channels < 2:
        audio_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                f"recording has {channels} channel(s); this system relies on "
                "stereo separation (left=agent, right=customer) instead of "
                "diarization, so a mono file cannot be attributed"
            ),
        )

    meta = CallMetadata(
        call_id=call_id,
        customer_id=slugify(customer_name),
        customer_name=customer_name.strip(),
        agent_id=slugify(agent_name),
        agent_name=agent_name.strip(),
        started_at=started_at or datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration,
        session="ingested",
        caller_mos=None,
        agent_mos=None,
    )

    return await run_in_threadpool(_run_pipeline, meta, audio_path)


def _run_pipeline(meta: CallMetadata, audio_path: Path):
    """Everything blocking, on a worker thread with its own DB connection."""
    from app.api.calls import get_call

    data_dir = Path(settings.data_dir)
    cache_dir, work_dir = run_batch.store.init_data_dirs(data_dir)
    conn = get_connection()

    try:
        try:
            run_batch.process_call(conn, meta, audio_path, cache_dir, work_dir)
        except Exception as e:
            _cleanup(conn, meta.call_id, audio_path)
            raise HTTPException(
                status_code=502, detail=f"transcription failed: {e}"
            ) from e

        try:
            median = _median_handle_time(conn)
            analyze.persist_analysis(
                conn, analyze.prepare_analysis(conn, meta.call_id, median)
            )
        except Exception as e:
            # The transcript is stored and useful on its own, so the call stays
            # — it simply shows as un-analysed rather than disappearing.
            raise HTTPException(
                status_code=502,
                detail=(
                    f"transcribed OK, but analysis failed: {e}. "
                    f"Call {meta.call_id} is stored."
                ),
            ) from e

        return get_call(meta.call_id, conn)
    finally:
        conn.close()


def _probe(path: Path) -> tuple[float, int]:
    """(duration_seconds, channel_count) via ffprobe, which ships in the image."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=channels", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400, detail=f"could not read audio: {result.stderr[:200]}"
        )

    channels, duration = 0, 0.0
    for line in result.stdout.split():
        value = line.strip()
        if not value:
            continue
        if "." in value:
            duration = float(value)
        else:
            channels = int(value)
    return duration, channels


def _median_handle_time(conn) -> float:
    rows = [
        r["duration_seconds"]
        for r in conn.execute("SELECT duration_seconds FROM calls ORDER BY duration_seconds")
    ]
    if not rows:
        return 0.0
    mid = len(rows) // 2
    return rows[mid] if len(rows) % 2 else (rows[mid - 1] + rows[mid]) / 2


def _cleanup(conn, call_id: str, audio_path: Path) -> None:
    """Leave nothing half-ingested behind when the pipeline fails."""
    with conn:
        conn.execute("DELETE FROM evidence WHERE call_id = ?", (call_id,))
        conn.execute("DELETE FROM turns WHERE call_id = ?", (call_id,))
        conn.execute("DELETE FROM calls WHERE id = ?", (call_id,))
    audio_path.unlink(missing_ok=True)
    shutil.rmtree(Path(settings.data_dir) / "work" / call_id, ignore_errors=True)
