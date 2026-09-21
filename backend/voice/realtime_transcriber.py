"""
ORION Realtime Voice Transcriber

Captures microphone audio with PyAudio and streams
it to AssemblyAI v3 for real-time transcription.

This module handles speech-to-text only.
It does NOT run ORION investigations.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

import pyaudio

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
from dotenv import load_dotenv


load_dotenv()

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_FRAMES = 800
FORMAT = pyaudio.paInt16


class ORIONRealtimeTranscriber:
    """
    AssemblyAI v3 microphone streaming.

    Non-blocking: start() launches a background thread.
    stop() shuts it down cleanly.
    """

    def __init__(
        self,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not api_key:
            raise RuntimeError("ASSEMBLYAI_API_KEY is not set in backend/.env")

        self.api_key = api_key

        self.on_partial = on_partial
        self.on_final = on_final
        self.on_status = on_status
        self.on_error = on_error

        self.transcriber: Optional[RealTimeTranscriber] = None
        self.audio: Optional[pyaudio.PyAudio] = None
        self.microphone = None

        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)

    def _error(self, message: str) -> None:
        if self.on_error:
            self.on_error(message)

    # ------------------------------------------------------------------
    # AssemblyAI event handlers
    # ------------------------------------------------------------------

    def _handle_begin(self, _client, event: BeginEvent) -> None:
        session_id = getattr(event, "id", "unknown")
        self._status(f"Voice session started: {session_id}")

    def _handle_turn(self, _client, event: TurnEvent) -> None:
        text = (getattr(event, "transcript", "") or "").strip()
        if not text:
            return

        if getattr(event, "end_of_turn", False):
            self._status("Speech recognized.")
            if self.on_final:
                self.on_final(text)
        else:
            if self.on_partial:
                self.on_partial(text)

    def _handle_terminated(self, _client, _event: TerminationEvent) -> None:
        self._status("Voice session ended.")

    def _handle_error(self, _client, error: RealTimeError) -> None:
        self._error(str(error))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running and self._thread is None:
            return

        self._running = False

        try:
            if self.microphone is not None:
                try:
                    self.microphone.stop_stream()
                except Exception:
                    pass
                try:
                    self.microphone.close()
                except Exception:
                    pass
                self.microphone = None

            if self.audio is not None:
                try:
                    self.audio.terminate()
                except Exception:
                    pass
                self.audio = None

            if self.transcriber is not None:
                try:
                    self.transcriber.disconnect(terminate=True)
                except TypeError:
                    try:
                        self.transcriber.disconnect()
                    except Exception:
                        pass
                except Exception:
                    pass
                self.transcriber = None
        finally:
            if self._thread is not None:
                self._thread.join(timeout=3.0)
                self._thread = None

        self._status("Voice stopped.")

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            # 1. Create AssemblyAI transcriber
            self.transcriber = RealTimeTranscriber(
                RealTimeTranscriberOptions(),
                api_key=self.api_key,
            )

            self.transcriber.on(RealTimeEvents.Begin, self._handle_begin)
            self.transcriber.on(RealTimeEvents.Turn, self._handle_turn)
            self.transcriber.on(RealTimeEvents.Termination, self._handle_terminated)
            self.transcriber.on(RealTimeEvents.Error, self._handle_error)

            # 2. Connect to AssemblyAI
            self.transcriber.connect(
    RealTimeParameters(
        sample_rate=SAMPLE_RATE,
        language="en",
    )
)

            # 3. Open microphone with PyAudio
            self.audio = pyaudio.PyAudio()
            self.microphone = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_FRAMES,
            )

            self._status("Microphone listening.")

            # 4. Stream mic audio to AssemblyAI until stopped
            while self._running:
                chunk = self.microphone.read(
                    CHUNK_FRAMES,
                    exception_on_overflow=False,
                )
                self.transcriber.stream(chunk)
                # Small pacing sleep prevents buffer overrun
                time.sleep(CHUNK_FRAMES / SAMPLE_RATE / 2)

        except Exception as error:
            self._error(f"Voice worker error: {error}")
        finally:
            self._running = False
            # Auto-cleanup if the worker dies unexpectedly
            try:
                if self.microphone is not None:
                    self.microphone.stop_stream()
                    self.microphone.close()
                    self.microphone = None
                if self.audio is not None:
                    self.audio.terminate()
                    self.audio = None
                if self.transcriber is not None:
                    try:
                        self.transcriber.disconnect(terminate=True)
                    except Exception:
                        pass
                    self.transcriber = None
            except Exception:
                pass