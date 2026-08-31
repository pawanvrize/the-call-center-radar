from app.config import settings

from .assemblyai_provider import AssemblyAIProvider
from .base import CHANNEL_SPEAKERS, Segment, Speaker, Transcriber, Word
from .whisper_provider import WhisperProvider


def get_transcriber(provider: str | None = None) -> Transcriber:
    provider = provider or settings.transcriber_provider

    if provider == "assemblyai":
        # Job ids live beside the transcript cache so an interrupted batch
        # resumes paid-for jobs instead of re-submitting them.
        from pathlib import Path

        return AssemblyAIProvider(
            api_key=settings.assemblyai_api_key,
            job_dir=Path(settings.data_dir) / "cache",
        )
    if provider == "whisper":
        return WhisperProvider(
            model_size=settings.whisper_model_size,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    raise ValueError(
        f"unknown transcriber provider: {provider!r} (expected 'assemblyai' or 'whisper')"
    )


__all__ = [
    "CHANNEL_SPEAKERS",
    "AssemblyAIProvider",
    "Segment",
    "Speaker",
    "Transcriber",
    "WhisperProvider",
    "Word",
    "get_transcriber",
]
