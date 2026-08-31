"""Primary transcription provider — AssemblyAI in multichannel mode.

Spends the free-tier credit on the commodity step (transcription + word
timestamps) so engineering time goes into the grounded intelligence layer.

Multichannel, NOT diarization. These are different features and the distinction
is the point:

  multichannel=True   transcribes each channel separately and tags every
                      utterance with its channel. Deterministic. Left channel
                      IS the agent — there is nothing to infer.

  speaker_labels=True ML diarization over a mono mix. Guesses speaker
                      boundaries, returns anonymous "Speaker A"/"B" that you
                      then have to map back to roles yourself.

Enabling diarization here would add error to a problem the recording format
already solves perfectly, and charge extra for it. Do not.

Also deliberately skips AssemblyAI's Sentiment Analysis / Auto Chapters /
Summarization add-ons: those judgments aren't grounded to a citation this
system controls and verifies, which is the entire architecture.

--- Why this submits and polls instead of calling transcribe() ---

The SDK's blocking `transcribe()` uploads, polls, and returns — but if anything
times out, the job ID is lost while the job keeps running on AssemblyAI's side
and is still billed. A first full-batch attempt at 10 workers hit the SDK's
30-second default `http_timeout` on essentially every call and orphaned ~200
completed, paid-for transcripts that could never be retrieved.

So: submit first, persist the job ID immediately, then poll. A timeout, a
crash, or a Ctrl-C now costs nothing — the next run finds the saved ID and
collects the finished transcript instead of paying for it twice.
"""
import json
import logging
import time
from pathlib import Path

from .base import CHANNEL_SPEAKERS, Segment, Speaker, Transcriber, Word

#: The SDK default is 30s, which concurrent uploads blow straight through.
HTTP_TIMEOUT_SECONDS = 300.0

#: How long to wait for one call's transcript before giving up. Calls here
#: average 58 seconds of audio, so this is very generous.
POLL_TIMEOUT_SECONDS = 900.0
POLL_INTERVAL_SECONDS = 3.0


class AssemblyAIProvider(Transcriber):
    name = "assemblyai"

    def __init__(self, api_key: str, job_dir: Path | None = None):
        if not api_key:
            raise ValueError(
                "ASSEMBLYAI_API_KEY is not set. Set it in .env, or switch to "
                "TRANSCRIBER_PROVIDER=whisper to run fully offline."
            )

        import assemblyai as aai

        aai.settings.api_key = api_key
        aai.settings.http_timeout = HTTP_TIMEOUT_SECONDS
        self._aai = aai
        self._transcriber = aai.Transcriber()
        self._job_dir = job_dir

    # -- job-id bookkeeping ------------------------------------------------

    def _job_file(self, call_id: str) -> Path | None:
        if self._job_dir is None:
            return None
        return self._job_dir / f"{call_id}.assemblyai.job"

    def _load_job_id(self, call_id: str) -> str | None:
        path = self._job_file(call_id)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))["id"]
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            return None

    def _save_job_id(self, call_id: str, job_id: str) -> None:
        path = self._job_file(call_id)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": job_id}), encoding="utf-8")

    def _clear_job_id(self, call_id: str) -> None:
        path = self._job_file(call_id)
        if path is not None:
            path.unlink(missing_ok=True)

    # -- transcription -----------------------------------------------------

    def transcribe_call(self, stereo_path: Path, work_dir: Path) -> list[Segment]:
        """One job for the whole stereo file. No channel splitting needed."""
        call_id = stereo_path.stem
        transcript = self._resume_or_submit(call_id, stereo_path)
        transcript = self._await_completion(transcript, call_id)

        segments = self._to_segments(transcript)
        if not segments:
            raise RuntimeError(
                f"AssemblyAI returned no utterances for {stereo_path.name}. "
                "Check that multichannel is enabled and the file really is stereo."
            )

        # Only now is the result safely in hand; the job no longer needs resuming.
        self._clear_job_id(call_id)
        return segments

    def _resume_or_submit(self, call_id: str, stereo_path: Path):
        existing = self._load_job_id(call_id)
        if existing:
            try:
                return self._aai.Transcript.get_by_id(existing)
            except Exception as e:
                # The saved job is gone or unreadable — fall through and
                # resubmit. Logged, not raised: a resubmit is the correct
                # recovery for one dead job id, but if this starts firing on
                # every call it means something systemic (bad API key,
                # account issue) and that needs to be visible, not silent.
                logging.getLogger(__name__).info(
                    "AssemblyAI job %s for %s unresumable (%s: %s) — resubmitting",
                    existing, call_id, type(e).__name__, e,
                )
                self._clear_job_id(call_id)

        config = self._aai.TranscriptionConfig(
            multichannel=True, punctuate=True, format_text=True
        )
        transcript = self._transcriber.submit(str(stereo_path), config=config)
        # Persisted BEFORE any polling, so a timeout can never orphan a paid job.
        self._save_job_id(call_id, transcript.id)
        return transcript

    def _await_completion(self, transcript, call_id: str):
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
        while True:
            status = transcript.status
            if status == self._aai.TranscriptStatus.completed:
                return transcript
            if status == self._aai.TranscriptStatus.error:
                self._clear_job_id(call_id)
                raise RuntimeError(f"AssemblyAI failed for {call_id}: {transcript.error}")
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"AssemblyAI job {transcript.id} for {call_id} still {status} "
                    f"after {POLL_TIMEOUT_SECONDS:.0f}s — re-run to resume it free"
                )

            time.sleep(POLL_INTERVAL_SECONDS)
            transcript = self._aai.Transcript.get_by_id(transcript.id)

    def _to_segments(self, transcript) -> list[Segment]:
        segments: list[Segment] = []
        for utterance in transcript.utterances or []:
            words = [
                Word(
                    text=w.text,
                    start=w.start / 1000,
                    end=w.end / 1000,
                    confidence=getattr(w, "confidence", 1.0),
                )
                for w in (utterance.words or [])
            ]
            segments.append(
                Segment(
                    speaker=self._speaker_for(utterance),
                    start=utterance.start / 1000,
                    end=utterance.end / 1000,
                    text=utterance.text,
                    words=words,
                )
            )
        return segments

    @staticmethod
    def _speaker_for(utterance) -> Speaker:
        """Map an utterance's channel to a role.

        `channel` is the authoritative field in multichannel mode. It arrives as
        either an int or a string depending on SDK version, so normalize. Fall
        back to `speaker` ("A"/"B") only if channel is absent.
        """
        channel = getattr(utterance, "channel", None)
        if channel is not None:
            try:
                return CHANNEL_SPEAKERS[int(channel)]
            except (ValueError, TypeError, KeyError):
                # channel present but not 1/2 — an SDK/API change, not the
                # documented multichannel contract. Silently falling through
                # to the speaker-label heuristic below would mislabel every
                # turn in the call with no signal anywhere that it happened,
                # exactly the failure mode the 35-call channel-swap bug was.
                logging.getLogger(__name__).warning(
                    "AssemblyAI utterance had an unexpected channel value %r "
                    "(text: %r) — falling back to the speaker-label heuristic",
                    channel, str(getattr(utterance, "text", ""))[:80],
                )

        speaker = str(getattr(utterance, "speaker", "") or "").strip().upper()
        return "agent" if speaker in ("A", "1") else "customer"
