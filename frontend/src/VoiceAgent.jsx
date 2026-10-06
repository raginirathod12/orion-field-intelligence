import { useEffect, useRef, useState } from "react";

const API_URL = "http://127.0.0.1:8000";
const SOCKET_URL = "wss://agents.assemblyai.com/v1/ws";
const TARGET_RATE = 24000;
const DEBUG = true;

export default function VoiceAgent({ onEvent, disabled = false }) {
  const [status, setStatus] = useState("IDLE");
  const [userTranscript, setUserTranscript] = useState("");
  const [agentTranscript, setAgentTranscript] = useState("");
  const [error, setError] = useState("");
  const [active, setActive] = useState(false);

  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const workletRef = useRef(null);

  // Playback — scheduled, gap-free
  const playbackContextRef = useRef(null);
  const nextPlayTimeRef = useRef(0);
  const activeSourcesRef = useRef([]);

  const pendingToolsRef = useRef([]);
  const stoppedByUserRef = useRef(false);
  const awaitingToolResultRef = useRef(false);

  // ==========================================================
  // Cleanup
  // ==========================================================

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

  function cleanupPlayback() {
    for (const s of activeSourcesRef.current) {
      try {
        s.stop();
      } catch {}
    }
    activeSourcesRef.current = [];
    nextPlayTimeRef.current = 0;

    if (playbackContextRef.current) {
      try {
        playbackContextRef.current.close();
      } catch {}
      playbackContextRef.current = null;
    }
  }

  function cleanupSocket() {
    const socket = socketRef.current;
    if (!socket) return;
    try {
      if (socket.readyState === WebSocket.OPEN) {
        try {
          socket.send(JSON.stringify({ type: "session.end" }));
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
    cleanupPlayback();
    cleanupSocket();
  }

  // ==========================================================
  // Playback
  // ==========================================================

  function flushPlayback() {
    for (const s of activeSourcesRef.current) {
      try {
        s.stop();
      } catch {}
    }
    activeSourcesRef.current = [];
    if (playbackContextRef.current) {
      nextPlayTimeRef.current = playbackContextRef.current.currentTime;
    }
  }

  function getPlaybackContext() {
    if (!playbackContextRef.current) {
      const ctx = new AudioContext({ sampleRate: TARGET_RATE });
      playbackContextRef.current = ctx;
      nextPlayTimeRef.current = ctx.currentTime + 0.25;
      console.log("Playback context sample rate:", ctx.sampleRate);
    }
    return playbackContextRef.current;
  }

  async function enqueueAudioChunk(base64Pcm) {
    if (!base64Pcm) return;

    try {
      const binary = atob(base64Pcm);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }

      const pcm16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i += 1) {
        float32[i] = pcm16[i] / 32768.0;
      }

      const ctx = getPlaybackContext();

      if (ctx.state === "suspended") {
        await ctx.resume();
      }

      const buffer = ctx.createBuffer(1, float32.length, TARGET_RATE);
      buffer.copyToChannel(float32, 0);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);

      const now = ctx.currentTime;
      const startAt = Math.max(nextPlayTimeRef.current, now + 0.02);
      source.start(startAt);
      nextPlayTimeRef.current = startAt + buffer.duration;

      activeSourcesRef.current.push(source);

      source.onended = () => {
        activeSourcesRef.current = activeSourcesRef.current.filter(
          (s) => s !== source,
        );
      };
    } catch (err) {
      console.warn("Audio decode failed:", err);
    }
  }

  // ==========================================================
  // Tool execution + polling for background investigation
  // ==========================================================

  async function executeTool(callId, name, args) {
    if (onEvent) {
      onEvent({
        type: "tool_call_start",
        name,
        arguments: args,
      });
    }

    try {
      const response = await fetch(`${API_URL}/voice/agent-tool`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, arguments: args || {} }),
      });

      if (!response.ok) throw new Error(`Tool HTTP ${response.status}`);

      const data = await response.json();
      const result = data.spoken || "Done.";

      if (onEvent) {
        onEvent({ type: "tool_result", name, arguments: args, result: data });
      }

      pendingToolsRef.current.push({
        call_id: callId,
        result: JSON.stringify({ spoken: result }),
      });

      // If this started a background investigation, poll for the result
      if (name === "start_investigation" && data.investigation_id) {
        pollInvestigation(data.investigation_id);
      }
    } catch (err) {
      console.error("Tool execution failed:", err);
      pendingToolsRef.current.push({
        call_id: callId,
        result: JSON.stringify({
          spoken: "I couldn't complete that tool.",
          error: String(err),
        }),
      });
    }
  }

  async function pollInvestigation(investigationId) {
    const maxAttempts = 60; // up to 90 seconds
    const intervalMs = 1500;

    for (let i = 0; i < maxAttempts; i += 1) {
      await new Promise((r) => setTimeout(r, intervalMs));

      try {
        const res = await fetch(
          `${API_URL}/voice/investigation-status/${investigationId}`,
        );
        const data = await res.json();

        if (data.status === "complete") {
          // Notify App so UI panels update
          if (onEvent) {
            onEvent({
              type: "tool_result",
              name: "investigate",
              arguments: { query: data.query },
              result: data,
            });
          }

          // Inject the result back into the voice session
          const prompt =
            `The investigation has completed. ` +
            `Here is the result: ${data.spoken} ` +
            `Now relay this to the user in your own voice. ` +
            `Include the real numbers and process name. ` +
            `End by asking: "Would you like me to suspend it and measure the system?"`;

          injectAgentPrompt(prompt);
          return;
        }
      } catch (err) {
        console.warn("Poll failed:", err);
      }
    }

    console.warn("Investigation polling timed out");
  }

  function injectAgentPrompt(text) {
    const s = socketRef.current;
    if (!s || s.readyState !== WebSocket.OPEN) return;

    try {
      s.send(
        JSON.stringify({
          type: "input.text",
          text: text,
        }),
      );
      console.log("Injected result into voice session");
    } catch (err) {
      console.warn("input.text failed, trying conversation.item.create:", err);
      try {
        s.send(
          JSON.stringify({
            type: "conversation.item.create",
            item: {
              type: "message",
              role: "user",
              content: [{ type: "input_text", text: text }],
            },
          }),
        );
        s.send(JSON.stringify({ type: "reply.create" }));
      } catch (err2) {
        console.warn("Both injection methods failed:", err2);
      }
    }
  }

  // ==========================================================
  // WebSocket messages
  // ==========================================================

  function handleMessage(event) {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }

    const type = message.type || "";
    if (DEBUG) console.log("[voice-agent]", type, message);

    switch (type) {
      case "session.ready":
        setStatus("LISTENING");
        break;

      case "session.updated":
        break;

      case "input.speech.started":
        setStatus("USER_SPEAKING");
        setUserTranscript("");
        awaitingToolResultRef.current = false;
        flushPlayback();
        break;

      case "transcript.user.delta":
        setUserTranscript((prev) =>
          (prev + " " + (message.delta || "")).trim(),
        );
        break;

      case "transcript.user":
        setUserTranscript(message.text || "");
        break;

      case "reply.started":
        setStatus("AGENT_SPEAKING");
        setAgentTranscript("");
        break;

      case "reply.audio":
        if (awaitingToolResultRef.current) {
          if (DEBUG) console.log("Dropping audio — awaiting tool result");
          return;
        }
        enqueueAudioChunk(message.data || message.audio || "");
        break;

      case "transcript.agent":
        setAgentTranscript(message.text || "");
        break;

      case "tool.call":
        awaitingToolResultRef.current = true;
        executeTool(message.call_id, message.name, message.arguments);
        break;

      case "reply.done": {
        const interrupted = message.status === "interrupted";

        if (interrupted) {
          flushPlayback();
          pendingToolsRef.current = [];
          awaitingToolResultRef.current = false;
          setStatus("LISTENING");
        } else {
          const socket = socketRef.current;
          if (socket && socket.readyState === WebSocket.OPEN) {
            for (const t of pendingToolsRef.current) {
              try {
                socket.send(
                  JSON.stringify({
                    type: "tool.result",
                    call_id: t.call_id,
                    result: t.result,
                  }),
                );
              } catch {}
            }
          }
          pendingToolsRef.current = [];
          awaitingToolResultRef.current = false;
          setStatus("LISTENING");
        }
        break;
      }

      case "session.error":
        setError(
          `Session error: ${message.code || "unknown"} ${message.message || ""}`,
        );
        break;

      case "session.ended":
        setStatus("ENDED");
        break;

      default:
        break;
    }
  }

  // ==========================================================
  // Start / stop
  // ==========================================================

  async function start() {
    if (active || disabled) return;

    setError("");
    setStatus("CONNECTING");
    setUserTranscript("");
    setAgentTranscript("");
    setActive(true);
    stoppedByUserRef.current = false;
    pendingToolsRef.current = [];

    try {
      const tokenResponse = await fetch(`${API_URL}/voice/agent-token`);
      if (!tokenResponse.ok)
        throw new Error("Unable to fetch voice agent token.");

      const config = await tokenResponse.json();
      const token = config.token;
      if (!token) throw new Error("No token returned from backend.");

      const url = `${SOCKET_URL}?token=${encodeURIComponent(token)}`;
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = async () => {
        const update = {
          type: "session.update",
          session: {
            system_prompt: config.system_prompt || "You are ORION.",
            greeting:
              config.greeting ||
              "Hi, I'm ORION. I investigate why your computer is running slowly and prove my answers with real measurements. What's going on?",
            tools: config.tools || [],
            input: {
              format: { encoding: "audio/pcm" },
            },
            output: {
              voice: "mary",
              format: { encoding: "audio/pcm" },
            },
          },
        };

        console.log("Sending session.update:", JSON.stringify(update, null, 2));
        socket.send(JSON.stringify(update));

        await startMic(socket);
      };

      socket.onmessage = handleMessage;

      socket.onerror = () => {
        setError("Voice agent connection failed.");
        setStatus("ERROR");
      };

      socket.onclose = () => {
        cleanupAudio();
        cleanupPlayback();
        if (!stoppedByUserRef.current) setStatus("IDLE");
      };
    } catch (err) {
      console.error("start() failed:", err);
      setError(err.message || "Unable to start voice agent.");
      setStatus("ERROR");
      cleanup();
      setActive(false);
    }
  }

  async function startMic(socket) {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    streamRef.current = stream;

    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;
    if (audioContext.state === "suspended") await audioContext.resume();

    const actualRate = audioContext.sampleRate;
    if (DEBUG) console.log("Mic sample rate:", actualRate);

    await audioContext.audioWorklet.addModule("/audio/pcm-processor-24k.js");

    const source = audioContext.createMediaStreamSource(stream);
    sourceRef.current = source;

    const worklet = new AudioWorkletNode(audioContext, "pcm-processor-24k", {
      processorOptions: { sourceRate: actualRate, targetRate: TARGET_RATE },
    });
    workletRef.current = worklet;

    worklet.port.onmessage = (event) => {
      const s = socketRef.current;
      if (!s || s.readyState !== WebSocket.OPEN) return;

      try {
        const bytes = new Uint8Array(event.data);
        const chunkSize = 0x8000;
        let binary = "";
        for (let i = 0; i < bytes.length; i += chunkSize) {
          binary += String.fromCharCode.apply(
            null,
            bytes.subarray(i, i + chunkSize),
          );
        }
        const base64 = btoa(binary);

        s.send(JSON.stringify({ type: "input.audio", audio: base64 }));
      } catch (err) {
        console.warn("Audio send failed:", err);
      }
    };

    source.connect(worklet);
  }

  function stop() {
    stoppedByUserRef.current = true;
    setStatus("STOPPING");
    cleanup();
    setActive(false);
    setStatus("IDLE");
  }

  useEffect(() => {
    return () => {
      stoppedByUserRef.current = true;
      cleanup();
    };
  }, []);

  // ==========================================================
  // Render
  // ==========================================================

  return (
    <section className="panel voice-agent-panel">
      <div className="panel-label">VOICE AGENT (REAL-TIME)</div>

      <div className="voice-agent-header">
        <div>
          <h2>Talk with ORION</h2>
          <div className="voice-agent-subtitle">
            Real-time, interruptible voice. Speak naturally. Cut ORION off if
            you want.
          </div>
        </div>
        <div className="voice-agent-status">{status}</div>
      </div>

      <div className="voice-agent-controls">
        {!active ? (
          <button
            type="button"
            className="voice-agent-button"
            onClick={start}
            disabled={disabled}
          >
            🎙 START VOICE AGENT
          </button>
        ) : (
          <button
            type="button"
            className="voice-agent-button stop"
            onClick={stop}
          >
            ■ END SESSION
          </button>
        )}
      </div>

      {active && (
        <div className="voice-agent-transcripts">
          <div className="voice-agent-line">
            <span className="voice-agent-role">YOU</span>
            <span>{userTranscript || "…"}</span>
          </div>
          <div className="voice-agent-line agent">
            <span className="voice-agent-role">ORION</span>
            <span>{agentTranscript || "…"}</span>
          </div>
        </div>
      )}

      {error && <div className="voice-agent-error">{error}</div>}
    </section>
  );
}
