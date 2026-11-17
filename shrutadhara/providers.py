"""Provider boundary; agy is the only supported adapter and never falls back.

Selection is local. Adapters retain their existing consent and capability gates;
constructing/listing an adapter does not probe it or contact a hosted service.
"""

from pathlib import Path
from typing import Protocol

from . import agy
from .core import MeetingError


class CapabilityRefusal(MeetingError):
    """A session-fatal refusal to process native audio; never submit later chunks."""


class Provider(Protocol):
    def identity(self, cfg: dict) -> dict: ...

    def capable(self, cfg: dict) -> bool: ...

    def transcribe(
        self, path: Path, duration: float, workspace: Path, cfg: dict
    ) -> dict: ...

    def structured(
        self, prompt: str, schema: dict, workspace: Path, cfg: dict
    ) -> dict: ...


class AgyProvider:
    """Delegate to the existing adapter without changing identity or policy."""

    def identity(self, cfg: dict) -> dict:
        return agy.identity(cfg)

    def capable(self, cfg: dict) -> bool:
        return agy.capable(cfg)

    def transcribe(
        self, path: Path, duration: float, workspace: Path, cfg: dict
    ) -> dict:
        return agy.invoke(
            agy.transcription_prompt(path, duration),
            agy.TRANSCRIPT_SCHEMA,
            workspace,
            cfg,
            audio_path=path,
        )

    def structured(self, prompt: str, schema: dict, workspace: Path, cfg: dict) -> dict:
        return agy.invoke(prompt, schema, workspace, cfg)


def get_provider(cfg: dict) -> Provider:
    if cfg.get("provider", "agy") != "agy":
        raise MeetingError("Unsupported AI provider; only agy is available", 3)
    return AgyProvider()


def available_providers() -> list[dict]:
    return [{"id": "agy", "description": "Existing agy CLI adapter", "default": True}]
