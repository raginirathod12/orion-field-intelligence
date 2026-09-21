"""
ORION Voice Session

Coordinates finalized transcripts with the ORION
investigation engine.

Contains no investigation logic itself.
"""

from __future__ import annotations

from typing import Any, Dict

from agents.orion_agent import orion


WAKE_WORD_PREFIXES = (
    "orion,",
    "orion ",
    "hey orion",
    "okay orion",
    "ok orion",
)


def _strip_wake_word(text: str) -> str:
    """
    Remove common wake-word prefixes so ORION receives
    a clean command.
    """
    lowered = text.lower()

    for prefix in WAKE_WORD_PREFIXES:
        if lowered.startswith(prefix):
            return text[len(prefix):].strip()

    return text.strip()


class ORIONVoiceSession:

    def process_transcript(self, transcript: str) -> Dict[str, Any]:
        cleaned = _strip_wake_word(transcript or "")

        if not cleaned:
            raise ValueError("Transcript is empty after cleaning.")

        return orion.process_structured(cleaned)