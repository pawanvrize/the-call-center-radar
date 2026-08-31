"""Transcript cache on disk.

The single most important performance decision in the build: transcription is
the only expensive, non-deterministic, money-spending step, and the analysis
layer downstream of it gets re-run many times while prompts and weights are
tuned. Caching the raw transcript before anything else touches it turns a
one-hour iteration loop into a ten-second one, and guarantees a re-run never
re-spends AssemblyAI credit on a call already transcribed.

Written keyed by (call_id, provider) so switching providers doesn't silently
serve you the other one's output.
"""
import json
from dataclasses import asdict
from pathlib import Path

from app.pipeline.transcribe.base import Segment, Word


def cache_path(cache_dir: Path, call_id: str, provider: str) -> Path:
    return cache_dir / f"{call_id}.{provider}.json"


def load(cache_dir: Path, call_id: str, provider: str) -> list[Segment] | None:
    path = cache_path(cache_dir, call_id, provider)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        segments = [
            Segment(
                speaker=s["speaker"],
                start=s["start"],
                end=s["end"],
                text=s["text"],
                words=[Word(**w) for w in s.get("words", [])],
            )
            for s in raw["segments"]
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        # A truncated write (killed mid-batch) or a stale/mismatched cache
        # format should not poison every re-run — just re-transcribe.
        path.unlink(missing_ok=True)
        return None

    return segments


def store(cache_dir: Path, call_id: str, provider: str, segments: list[Segment]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, call_id, provider)
    payload = {"call_id": call_id, "provider": provider,
               "segments": [asdict(s) for s in segments]}
    # Write-then-rename: a killed batch never leaves a half-written cache entry.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)
