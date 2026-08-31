"""Offline fallback provider — faster-whisper (CTranslate2).

Zero API key, zero network dependency. This is what keeps the README's "runs
from scratch" claim true regardless of credit balance, and the safety net if
the live demo needs to work without network.

Whisper can only see one speaker at a time, so this provider implements
transcribe_call by splitting channels and transcribing each independently. That
is still exact speaker attribution — each channel is single-speaker by
construction — just two passes instead of one.

Two settings matter more than they look on channel-split telephony:

  vad_filter                 each channel is ~50% silence (the customer channel
                             is empty while the agent talks). Without VAD,
                             Whisper hallucinates fluently into that silence.
  condition_on_previous_text=False
                             stops one hallucination from seeding the next.

Segments are additionally filtered on no_speech_prob, because VAD alone does
not catch everything.
"""
import logging
from pathlib import Path

from .base import Segment, Speaker, Transcriber, Word

#: Above this, treat the segment as silence the model talked over.
NO_SPEECH_THRESHOLD = 0.6


class WhisperProvider(Transcriber):
    name = "whisper"

    def __init__(self, model_size: str, device: str, compute_type: str):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None  # lazy — don't pay model load cost at import time

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe_call(self, stereo_path: Path, work_dir: Path) -> list[Segment]:
        from app.pipeline.audio import split_channels

        channels = split_channels(stereo_path, work_dir)
        agent_segments = self._transcribe_channel(channels.agent_wav, "agent")
        customer_segments = self._transcribe_channel(channels.customer_wav, "customer")

        # Matches assemblyai_provider's equivalent guard — a call with zero
        # turns on both sides is a transcription failure, not an empty call.
        if not agent_segments and not customer_segments:
            raise RuntimeError(
                f"Whisper produced no speech on either channel for {stereo_path.name}. "
                "Check the recording isn't silent/corrupted."
            )
        # One-sided emptiness is plausible (a customer who says nothing before
        # hanging up) but unusual enough to be worth a log line rather than
        # silently flowing downstream as a call with no evidence to cite on
        # that side — visibility over the same class of problem the AssemblyAI
        # channel-mapping fallback above logs.
        if not agent_segments or not customer_segments:
            empty_side = "agent" if not agent_segments else "customer"
            logging.getLogger(__name__).warning(
                "Whisper produced zero segments on the %s channel for %s",
                empty_side, stereo_path.name,
            )

        return [*agent_segments, *customer_segments]

    def _transcribe_channel(self, wav_path: Path, speaker: Speaker) -> list[Segment]:
        model = self._load()
        segments, _info = model.transcribe(
            str(wav_path),
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        result: list[Segment] = []
        for seg in segments:
            if getattr(seg, "no_speech_prob", 0.0) > NO_SPEECH_THRESHOLD:
                continue
            text = seg.text.strip()
            if not text:
                continue

            words = [
                Word(text=w.word.strip(), start=w.start, end=w.end, confidence=w.probability)
                for w in (seg.words or [])
            ]
            result.append(
                Segment(speaker=speaker, start=seg.start, end=seg.end, text=text, words=words)
            )
        return result
