import { useEffect, useRef, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

const TARGET_RATE = 16000;

const SOCKET_URL = "wss://streaming.assemblyai.com/v3/ws";

const DEBUG = true;

export default function VoiceInput({ onTranscript, disabled = false }) {
  const [status, setStatus] = useState("IDLE");
  const [partialTranscript, setPartialTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [error, setError] = useState("");

  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const workletRef = useRef(null);

  const stoppedByUserRef = useRef(false);
  const statusRef = useRef("IDLE");

  // Keep statusRef in sync with status state
  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  function cleanupAudio() {
    if (workletRef.current) {
      try {
        workletRef.current.port.postMessage({ type: "flush" });
      } catch {}
      try {
        workletRef.current.disconnect();
      } catch {}
      workletRef.current = null;
    }

    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch {}
      sourceRef.current = null;
    }

    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {}
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((t) => t.stop());
      } catch {}
      streamRef.current = null;
    }
  }

  function cleanupSocket() {
    const socket = socketRef.current;
    if (!socket) return;

    try {
      if (socket.readyState === WebSocket.OPEN) {
        // Some AssemblyAI versions accept Terminate; others just close.
        try {
          socket.send(JSON.stringify({ type: "Terminate" }));
        } catch {}
      }
    } catch {}

    try {
      socket.close();
    } catch {}

    socketRef.current = null;
  }

  function cleanup() {
    cleanupAudio();
    cleanupSocket();
  }

  async function startListening() {
    if (disabled || status === "LISTENING" || status === "CONNECTING") return;

    setError("");
    setPartialTranscript("");
    setFinalTranscript("");
    stoppedByUserRef.current = false;

    try {
      setStatus("CONNECTING");

      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support microphone access.");
      }

      // 1. Get short-lived token from backend
      const tokenResponse = await fetch(`${API_URL}/voice/token`);

      if (!tokenResponse.ok) {
        let detail = "Unable to create voice session.";
        try {
          const body = await tokenResponse.json();
          detail = body?.detail || detail;
        } catch {}
        throw new Error(detail);
      }

      const tokenData = await tokenResponse.json();
      const token = tokenData?.token;

      if (!token) {
        throw new Error("Voice token was not returned by the backend.");
      }

      // 2. Open WebSocket to AssemblyAI
      //    NOTE: We do NOT send speech_model here. It's set at token creation.
      const url =
        `${SOCKET_URL}` +
        `?token=${encodeURIComponent(token)}` +
        `&sample_rate=${TARGET_RATE}`;

      if (DEBUG) console.log("WS URL:", url);

      const socket = new WebSocket(url);
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;

      socket.onopen = async () => {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              channelCount: 1,
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });
          streamRef.current = stream;

          // 3. Audio context — try to force 16k, fall back gracefully
          let audioContext;
          try {
            audioContext = new AudioContext({ sampleRate: TARGET_RATE });
          } catch {
            audioContext = new AudioContext();
          }
          audioContextRef.current = audioContext;

          if (audioContext.state === "suspended") {
            await audioContext.resume();
          }

          const actualRate = audioContext.sampleRate;
          if (DEBUG) console.log("AudioContext sampleRate:", actualRate);

          await audioContext.audioWorklet.addModule("/audio/pcm-processor.js");

          const source = audioContext.createMediaStreamSource(stream);
          sourceRef.current = source;

          const worklet = new AudioWorkletNode(audioContext, "pcm-processor", {
            processorOptions: {
              sourceRate: actualRate,
              targetRate: TARGET_RATE,
            },
          });
          workletRef.current = worklet;

          worklet.port.onmessage = (event) => {
            const s = socketRef.current;
            if (!s || s.readyState !== WebSocket.OPEN) return;
            try {
              s.send(event.data);
            } catch (sendErr) {
              if (DEBUG) console.error("WS send failed:", sendErr);
            }
          };

          source.connect(worklet);
          // NOTE: do NOT connect worklet to destination — that causes echo.

          setStatus("LISTENING");
        } catch (micError) {
          setError(micError?.message || "Unable to access microphone.");
          setStatus("ERROR");
          cleanup();
        }
      };

      socket.onmessage = (event) => {
        let message;
        try {
          message = JSON.parse(event.data);
        } catch {
          return;
        }

        if (DEBUG) console.log("WS recv:", message);

        const type = message.type || message.Type || "";

        if (type === "Begin") {
          setStatus("LISTENING");
          return;
        }

        if (type === "Turn") {
          const transcript = (message.transcript || message.text || "").trim();
          if (!transcript) return;

          const endOfTurn =
            message.end_of_turn === true ||
            message.endOfTurn === true ||
            message.end_of_turn === "true";

          if (endOfTurn) {
            setFinalTranscript(transcript);
            setPartialTranscript("");
            setStatus("TRANSCRIPT READY");

            if (onTranscript) {
              onTranscript(transcript);
            }
          } else {
            setPartialTranscript(transcript);
          }
          return;
        }

        if (type === "Termination") {
          cleanupAudio();
          if (!stoppedByUserRef.current) {
            setStatus("SESSION ENDED");
          }
          return;
        }

        if (type === "Error") {
          const messageText =
            message.error || message.message || "AssemblyAI voice error.";
          setError(messageText);
          setStatus("ERROR");
        }
      };

      socket.onerror = (e) => {
        if (DEBUG) console.error("WS error event:", e);
        setError("Voice WebSocket connection failed.");
        setStatus("ERROR");
      };

      socket.onclose = (e) => {
        if (DEBUG) console.log("WS closed:", e.code, e.reason);
        cleanupAudio();

        // Use ref instead of stale closure for status
        if (!stoppedByUserRef.current && statusRef.current !== "ERROR") {
          setStatus("IDLE");
        }
      };
    } catch (requestError) {
      setError(requestError?.message || "Unable to start voice input.");
      setStatus("ERROR");
      cleanup();
    }
  }

  function stopListening() {
    stoppedByUserRef.current = true;
    setStatus("STOPPING");
    cleanup();
    setPartialTranscript("");
    setStatus("IDLE");
  }

  useEffect(() => {
    return () => {
      stoppedByUserRef.current = true;
      cleanup();
    };
  }, []);

  const listening = status === "LISTENING" || status === "CONNECTING";

  return (
    <section className="panel voice-panel">
      <div className="panel-label">ORION VOICE</div>

      <div className="voice-header">
        <div>
          <h2>Talk to ORION</h2>
          <div className="voice-subtitle">Speak an investigation request</div>
        </div>
        <div className="voice-status">{status}</div>
      </div>

      <div className="voice-controls">
        {!listening ? (
          <button
            type="button"
            className="voice-button"
            onClick={startListening}
            disabled={disabled}
          >
            🎙 START LISTENING
          </button>
        ) : (
          <button
            type="button"
            className="voice-button"
            onClick={stopListening}
          >
            ■ STOP LISTENING
          </button>
        )}
      </div>

      <div className="voice-transcript">
        <div className="voice-transcript-label">LIVE TRANSCRIPT</div>
        <div className="voice-transcript-text">
          {partialTranscript || finalTranscript || "Waiting for speech..."}
        </div>
      </div>

      {error && <div className="voice-error">{error}</div>}
    </section>
  );
}
