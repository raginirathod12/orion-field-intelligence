"""
ORION Voice Test

Live microphone test. Prints partial and final transcripts.

Run from `backend`:

    python -m voice.test_voice

Use this ONLY to verify the microphone path works.
For everyday testing, use test_voice_from_file.py instead.
"""

from __future__ import annotations

import time

from voice.realtime_transcriber import ORIONRealtimeTranscriber


def on_partial(text: str) -> None:
    print(f"\rPARTIAL: {text:<80}", end="", flush=True)


def on_final(text: str) -> None:
    print()
    print(f"FINAL:   {text}")


def on_status(message: str) -> None:
    print(f"\nSTATUS:  {message}")


def on_error(message: str) -> None:
    print(f"\nERROR:   {message}")


def main() -> None:
    print("=" * 60)
    print("ORION VOICE TEST (live microphone)")
    print("=" * 60)
    print()
    print("Speak into your microphone.")
    print("Press CTRL+C to stop.")
    print()

    transcriber = ORIONRealtimeTranscriber(
        on_partial=on_partial,
        on_final=on_final,
        on_status=on_status,
        on_error=on_error,
    )

    transcriber.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        transcriber.stop()


if __name__ == "__main__":
    main()