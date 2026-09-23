import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

const API_URL = "http://127.0.0.1:8000";
const TARGET_RATE = 16000;
const SOCKET_URL = "wss://streaming.assemblyai.com/v3/ws";
const DEBUG = false;

const VoiceInput = forwardRef(function VoiceInput(
  {
    onTranscript,
    disabled = false,
    autoStopOnFinal = false,
    hideControls = false,
  },
  ref,
) {
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
  const mountedRef = useRef(true);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

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
    if (
      disabled ||
      statusRef.current === "LISTENING" ||
      statusRef.current === "CONNECTING"
    ) {
      return;
    }

    setError("");
    setPartialTranscript("");
    setFinalTranscript("");
    stoppedByUserRef.current = false;

    try {
      setStatus("CONNECTING");

      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support microphone access.");
      }

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

      const url = `${SOCKET_URL}?token=${encodeURIComponent(token)}&sample_rate=${TARGET_RATE}`;
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
            } catch {}
          };

          source.connect(worklet);
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

            if (onTranscript) onTranscript(transcript);

            if (autoStopOnFinal) {
              setTimeout(() => {
                if (mountedRef.current) {
                  stoppedByUserRef.current = true;
                  cleanup();
                  setStatus("IDLE");
                }
              }, 400);
            }
          } else {
            setPartialTranscript(transcript);
          }
          return;
        }

        if (type === "Termination") {
          cleanupAudio();
          if (!stoppedByUserRef.current && mountedRef.current) {
            setStatus("IDLE");
          }
          return;
        }

        if (type === "Error") {
          const messageText =
            message.error || message.message || "Voice error.";
          setError(messageText);
          setStatus("ERROR");
        }
      };

      socket.onerror = () => {
        setError("Voice WebSocket connection failed.");
        setStatus("ERROR");
      };

      socket.onclose = () => {
        cleanupAudio();
        if (
          !stoppedByUserRef.current &&
          statusRef.current !== "ERROR" &&
          mountedRef.current
        ) {
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

  useImperativeHandle(ref, () => ({
    start: () => {
      const s = statusRef.current;
      if (
        s === "IDLE" ||
        s === "SESSION ENDED" ||
        s === "ERROR" ||
        s === "TRANSCRIPT READY"
      ) {
        setTimeout(() => {
          if (mountedRef.current) startListening();
        }, 100);
      }
    },
    stop: () => {
      const s = statusRef.current;
      if (s !== "IDLE" && s !== "SESSION ENDED") {
        stopListening();
      }
    },
    isActive: () => {
      const s = statusRef.current;
      return s === "LISTENING" || s === "CONNECTING";
    },
    getStatus: () => statusRef.current,
  }));

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

      {!hideControls && (
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
      )}

      <div className="voice-transcript">
        <div className="voice-transcript-label">LIVE TRANSCRIPT</div>
        <div className="voice-transcript-text">
          {partialTranscript || finalTranscript || "Waiting for speech..."}
        </div>
      </div>

      {error && <div className="voice-error">{error}</div>}
    </section>
  );
});

export default VoiceInput;
