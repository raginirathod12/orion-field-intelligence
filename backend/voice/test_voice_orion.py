"""
ORION Voice -> Investigation Test

Feeds a hardcoded transcript through ORIONVoiceSession
to prove voice-to-investigation works without a microphone.

Run from `backend`:

    python -m voice.test_voice_orion
"""

from __future__ import annotations

import json

from voice.voice_session import ORIONVoiceSession


def main() -> None:
    print("=" * 60)
    print("ORION VOICE -> INVESTIGATION TEST")
    print("=" * 60)

    transcript = "ORION, my laptop is extremely slow. Find out why."

    print()
    print(f"Raw transcript: {transcript}")

    session = ORIONVoiceSession()
    result = session.process_transcript(transcript)

    print()
    print("Result summary:")
    print(json.dumps(
        {
            "success": result.get("success"),
            "intent": result.get("intent"),
            "has_investigation": "investigation" in result,
            "diagnosis_confidence": (
                result.get("diagnosis") or {}
            ).get("confidence"),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()