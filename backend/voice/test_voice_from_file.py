"""
ORION Voice Test From File

Replays a prerecorded WAV through AssemblyAI (v3 SDK).

Run from `backend`:

    python -m voice.test_voice_from_file
    python -m voice.test_voice_from_file slow_laptop.wav
"""

from __future__ import annotations

import os
import sys
import time
import wave

from dotenv import load_dotenv

from assemblyai.streaming.v3 import (
    BeginEvent,
    RealTimeError,
    RealTimeEvents,
    RealTimeParameters,
    RealTimeTranscriber,
    RealTimeTranscriberOptions,
    TerminationEvent,
    TurnEvent,
)


load_dotenv()

SAMPLE_RATE = 16000
CHUNK_FRAMES = 800


def main() -> None:
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY not set in backend/.env")

    filename = sys.argv[1] if len(sys.argv) > 1 else "slow_laptop.wav"

    wav_path = os.path.join(
        os.path.dirname(__file__),
        "samples",
        filename,
    )

    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Missing WAV: {wav_path}")

    with wave.open(wav_path, "rb") as wav:
        if wav.getframerate() != SAMPLE_RATE:
            raise ValueError(f"WAV must be {SAMPLE_RATE} Hz")
        if wav.getnchannels() != 1:
            raise ValueError("WAV must be mono")
        if wav.getsampwidth() != 2:
            raise ValueError("WAV must be 16-bit PCM")

    finals: list[str] = []

    def on_begin(_client, event: BeginEvent):
        print(f"SESSION OPEN: {getattr(event, 'id', 'unknown')}")

    def on_turn(_client, event: TurnEvent):
        text = (getattr(event, "transcript", "") or "").strip()
        if not text:
            return

        if getattr(event, "end_of_turn", False):
            print(f"\nFINAL:   {text}")
            finals.append(text)
        else:
            print(f"\rPARTIAL: {text:<80}", end="", flush=True)

    def on_terminated(_client, _event: TerminationEvent):
        print("\nSESSION CLOSED")

    def on_error(_client, error: RealTimeError):
        print(f"\nERROR: {error}")

    transcriber = RealTimeTranscriber(
        RealTimeTranscriberOptions(),
        api_key=api_key,
    )

    transcriber.on(RealTimeEvents.Begin, on_begin)
    transcriber.on(RealTimeEvents.Turn, on_turn)
    transcriber.on(RealTimeEvents.Termination, on_terminated)
    transcriber.on(RealTimeEvents.Error, on_error)

    transcriber.connect(
        RealTimeParameters(sample_rate=SAMPLE_RATE)
    )

    print(f"Playing: {filename}")
    print("Streaming...")

    with wave.open(wav_path, "rb") as wav:
        while True:
            frames = wav.readframes(CHUNK_FRAMES)
            if not frames:
                break
            transcriber.stream(frames)
            time.sleep(CHUNK_FRAMES / SAMPLE_RATE)

    # Give AssemblyAI a moment to finalize the last turn
    time.sleep(1.5)

    try:
        transcriber.disconnect(terminate=True)
    except TypeError:
        transcriber.disconnect()

    print()
    print("=" * 60)
    print("COMBINED:", " ".join(finals))


if __name__ == "__main__":
    main()