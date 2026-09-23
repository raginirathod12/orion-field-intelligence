import { useMemo, useRef, useState, useEffect } from "react";
import "./App.css";
import InvestigationTimeline from "./InvestigationTimeline";
import ActionPanel from "./ActionPanel";
import VerificationResult from "./VerificationResult";
import InvestigationHistory from "./InvestigationHistory";
import VoiceInput from "./VoiceInput";
import "./investigation.css";

const API_URL = "http://127.0.0.1:8000";

const DEFAULT_MESSAGE = "My laptop is extremely slow. Find out why.";

const INVESTIGATION_STEPS = [
  ["understanding", "Understanding request"],
  ["telemetry", "Collecting telemetry"],
  ["anomaly_detection", "Detecting anomalies"],
  ["root_cause_analysis", "Ranking root causes"],
  ["investigation", "Investigating"],
  ["evidence_fusion", "Fusing evidence"],
  ["diagnosis", "Generating diagnosis"],
];

const PROTECTED_NAMES = new Set([
  "system",
  "system idle process",
  "registry",
  "smss.exe",
  "csrss.exe",
  "wininit.exe",
  "services.exe",
  "lsass.exe",
  "winlogon.exe",
  "svchost.exe",
  "fontdrvhost.exe",
  "dwm.exe",
  "explorer.exe",
  "conhost.exe",
  "memcompression",
]);

function formatNumber(value, decimals = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toFixed(decimals);
}

function formatStatus(value) {
  if (value === null || value === undefined || value === "") {
    return "UNKNOWN";
  }
  return String(value).replaceAll("_", " ").toUpperCase();
}

function formatClassification(value) {
  if (value === null || value === undefined || value === "") {
    return "UNCLASSIFIED";
  }
  return String(value).replaceAll("_", " ").toUpperCase();
}

function isActionable(evidence) {
  if (!evidence || !evidence.pid || !evidence.process) return false;
  if (PROTECTED_NAMES.has(String(evidence.process).toLowerCase())) return false;

  const classification = (evidence.classification || "").toUpperCase();
  if (["WEAKENED", "UNSUPPORTED", "NOT_CONFIRMED"].includes(classification)) {
    return false;
  }

  const score = Number(evidence.score ?? 0);
  if (score <= 0) return false;

  const confidence = (evidence.confidence || "").toUpperCase();
  if (confidence === "LOW") return false;

  return true;
}

// ========================================================
// SMALL TALK — PRIORITY 8 (personality)
// ========================================================

function parseSmallTalk(text) {
  const t = (text || "")
    .toLowerCase()
    .trim()
    .replace(/[.,!?;:]+$/g, "");

  if (!t) return null;

  // Greetings
  if (
    t === "hello" ||
    t === "hi" ||
    t === "hey" ||
    t === "hey orion" ||
    t === "hello orion" ||
    t.startsWith("hi ") ||
    t.startsWith("hello ") ||
    t.startsWith("hey ")
  ) {
    return {
      speech:
        "Hey, what can I help you with today? You can say something like 'my laptop is slow' and I'll take a look.",
    };
  }

  // How are you
  if (
    t.includes("how are you") ||
    t.includes("how you doing") ||
    t.includes("how's it going")
  ) {
    return {
      speech: "I'm ready. What's going on with your computer?",
    };
  }

  // What can you do / help
  if (
    t.includes("what can you do") ||
    t.includes("what do you do") ||
    t.includes("help me") ||
    t === "help" ||
    t.includes("what are you")
  ) {
    return {
      speech:
        "I investigate why your computer is running slowly. I look at CPU, memory, disk, and the processes running on your machine. Then I identify the most likely cause, ask your permission before taking any action, and prove whether fixing it actually helped. Try saying: my laptop is slow.",
    };
  }

  // Thank you
  if (
    t === "thanks" ||
    t === "thank you" ||
    t === "thanks orion" ||
    t === "thank you orion" ||
    t.startsWith("thanks ") ||
    t.startsWith("thank you ")
  ) {
    return {
      speech: "Anytime. Let me know if you need anything else.",
    };
  }

  // Goodbye
  if (
    t === "bye" ||
    t === "goodbye" ||
    t === "see you" ||
    t === "see ya" ||
    t.startsWith("bye ") ||
    t.startsWith("goodbye ")
  ) {
    return {
      speech: "Goodbye. Have a great day.",
      endConversation: true,
    };
  }

  // PRIORITY 8 — Personality responses
  if (
    t.includes("are you smart") ||
    t.includes("are you intelligent") ||
    t.includes("are you good") ||
    t.includes("are you clever")
  ) {
    return {
      speech:
        "I'm careful. I don't guess. I measure. Try me — ask why your computer is slow.",
    };
  }

  if (
    t.includes("are you real") ||
    t.includes("are you alive") ||
    t.includes("are you human")
  ) {
    return {
      speech:
        "I'm ORION — a program that investigates your computer with real measurements. I don't pretend to be human.",
    };
  }

  if (
    t.includes("you're wrong") ||
    t.includes("you are wrong") ||
    t.includes("that's wrong") ||
    t.includes("incorrect")
  ) {
    return {
      speech:
        "Possibly. I'm designed to be corrected. Run another investigation and we'll see what the measurements say.",
    };
  }

  if (
    t.includes("good job") ||
    t.includes("nice work") ||
    t.includes("well done") ||
    t.includes("you're good") ||
    t.includes("impressive")
  ) {
    return {
      speech:
        "Thanks. But the measurements did the real work — I just reported them honestly.",
    };
  }

  if (
    t.includes("what is your name") ||
    t.includes("what's your name") ||
    t.includes("who are you") ||
    t.includes("who made you") ||
    t.includes("who built you")
  ) {
    return {
      speech:
        "I'm ORION. I stand for evidence-based computer intelligence. I investigate why systems are slow and prove whether my answers are right.",
    };
  }

  if (
    t.includes("can you help") ||
    t.includes("i need help") ||
    t.includes("i have a problem")
  ) {
    return {
      speech:
        "I can. Tell me what's happening — for example, 'my laptop is slow' or 'Chrome is using too much memory'.",
    };
  }

  if (
    t === "okay" ||
    t === "ok" ||
    t === "cool" ||
    t === "great" ||
    t === "nice"
  ) {
    return {
      speech: "What would you like me to investigate?",
    };
  }

  return null;
}

function parseYesNo(text) {
  const t = text.toLowerCase().trim();

  const noWords = [
    "no",
    "nope",
    "nah",
    "don't",
    "do not",
    "cancel",
    "stop",
    "never mind",
    "nevermind",
    "negative",
    "not now",
  ];
  const yesWords = [
    "yes",
    "yeah",
    "yep",
    "sure",
    "do it",
    "go ahead",
    "confirm",
    "okay",
    "ok",
    "proceed",
    "affirmative",
    "absolutely",
    "please do",
    "please",
  ];

  if (
    noWords.some((w) => t === w || t.startsWith(w + " ") || t.endsWith(" " + w))
  ) {
    return "no";
  }
  if (
    yesWords.some(
      (w) => t === w || t.startsWith(w + " ") || t.endsWith(" " + w),
    )
  ) {
    return "yes";
  }
  return null;
}

function parseDone(text) {
  const t = text.toLowerCase().trim();
  const doneWords = [
    "no",
    "that's it",
    "thats it",
    "nothing",
    "nothing else",
    "done",
    "stop",
    "no thanks",
    "no thank you",
    "all good",
    "i'm good",
    "im good",
    "we're done",
    "were done",
  ];
  return doneWords.some(
    (w) => t === w || t.startsWith(w + " ") || t.includes(" " + w),
  );
}

// ========================================================
// FOLLOW-UP COMMANDS — PRIORITY 4
// ========================================================

function parseFollowUp(text) {
  const t = (text || "")
    .toLowerCase()
    .trim()
    .replace(/[.,!?;:]+$/g, "");

  if (!t) return null;

  if (
    t === "why" ||
    t.includes("tell me more") ||
    t.includes("explain") ||
    t.includes("more detail") ||
    t.includes("reasoning") ||
    t.includes("how do you know") ||
    t.includes("how did you find")
  ) {
    return "why";
  }

  if (
    t.includes("show me the data") ||
    t.includes("show me data") ||
    t.includes("give me the numbers") ||
    t.includes("what are the numbers") ||
    t.includes("raw data") ||
    t.includes("the numbers")
  ) {
    return "data";
  }

  if (
    t.includes("what else") ||
    t.includes("any other") ||
    t.includes("other candidates") ||
    t.includes("anything else") ||
    t.includes("other processes")
  ) {
    return "others";
  }

  if (
    t.includes("ignore that") ||
    t.includes("start over") ||
    t.includes("forget it") ||
    t.includes("forget that") ||
    t.includes("reset") ||
    t.includes("clear")
  ) {
    return "reset";
  }

  if (
    t.includes("investigate again") ||
    t.includes("try again") ||
    t.includes("run again") ||
    t.includes("do it again") ||
    t.includes("reinvestigate") ||
    t.includes("another investigation")
  ) {
    return "investigate_again";
  }

  return null;
}

function App() {
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeStep, setActiveStep] = useState(-1);
  const [showRawResponse, setShowRawResponse] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);

  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(true);
  const audioRef = useRef(null);

  // Conversation mode
  const [conversationActive, setConversationActive] = useState(false);
  const [conversationState, setConversationState] = useState("idle");
  const [conversationContext, setConversationContext] = useState(null);
  const [pendingIntervention, setPendingIntervention] = useState(null);
  const [lastTranscript, setLastTranscript] = useState(null);
  const voiceRef = useRef();

  // ========================================================
  // VOICE OUTPUT
  // ========================================================

  function buildVoiceSummary(result) {
    if (!result) return "";

    const diagnosis = result.diagnosis || {};
    const observation = diagnosis.observation || "";
    const confidence = diagnosis.confidence || "";
    const strongest = result?.investigation?.strongest_evidence;
    const evidenceList = result?.investigation?.evidence || [];

    let speech = "Alright, I found something interesting. ";

    const sentences = observation
      .split(/(?<=[.!?])\s+/)
      .filter(Boolean)
      .slice(0, 2);

    if (sentences.length > 0) {
      speech += sentences.join(" ").trim() + " ";
    }

    if (strongest?.process) {
      const name = strongest.process.replace(".exe", "");
      const cpu = strongest.cpu_percent;
      const score = strongest.score;
      const temporal = (strongest.temporal_behavior || "")
        .replaceAll("_", " ")
        .toLowerCase();
      const classification = (strongest.classification || "")
        .replaceAll("_", " ")
        .toLowerCase();

      speech += `The strongest candidate is ${name}`;

      if (cpu) {
        speech += `, currently using about ${Math.round(cpu)} percent CPU`;
      }

      if (
        temporal &&
        temporal !== "unknown" &&
        temporal !== "no temporal data"
      ) {
        speech += `. Its usage pattern looks ${temporal}`;
      }

      if (classification) {
        speech += `, so I'm classifying it as a ${classification}`;
      }

      if (score) {
        speech += `. The evidence score is ${Math.round(score)} out of one hundred`;
      }

      speech += ". ";
    }

    if (evidenceList.length > 1) {
      const others = evidenceList.length - 1;
      speech += `I also found ${others} other process${others > 1 ? "es" : ""} with activity, but none as significant. `;
    }

    const conf = (confidence || "").toLowerCase();
    if (conf === "high") {
      speech +=
        "My confidence is high. The evidence strongly points to this being the main cause. ";
    } else if (conf === "moderate") {
      speech +=
        "My confidence is moderate. The evidence points this way, but I'd like to verify with a measurement. ";
    } else if (conf === "low") {
      speech +=
        "My confidence is low. I have some evidence, but I'm not certain yet. ";
    }

    return speech.trim();
  }

  function fallbackBrowserTTS(text, done) {
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      const voices = window.speechSynthesis.getVoices();
      const english = voices.find((v) => v.lang.startsWith("en"));
      if (english) utterance.voice = english;

      let finished = false;
      const safeDone = () => {
        if (!finished) {
          finished = true;
          done();
        }
      };

      utterance.onend = safeDone;
      utterance.onerror = safeDone;
      setTimeout(safeDone, 15000);
      window.speechSynthesis.speak(utterance);
    } catch {
      done();
    }
  }

  function speakText(text) {
    return new Promise((resolve) => {
      if (!text || !voiceOutputEnabled) {
        resolve();
        return;
      }

      const clean = String(text)
        .replace(/[*#_`>|]/g, "")
        .slice(0, 900)
        .trim();

      if (!clean) {
        resolve();
        return;
      }

      if (audioRef.current) {
        try {
          audioRef.current.pause();
          audioRef.current.currentTime = 0;
        } catch {}
        audioRef.current = null;
      }

      let resolved = false;
      const safeResolve = () => {
        if (!resolved) {
          resolved = true;
          resolve();
        }
      };

      const timeout = setTimeout(safeResolve, 90000);

      try {
        const url = `${API_URL}/tts/speak?text=${encodeURIComponent(clean)}`;
        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          clearTimeout(timeout);
          safeResolve();
        };
        audio.onerror = () => {
          clearTimeout(timeout);
          fallbackBrowserTTS(clean, safeResolve);
        };

        audio.play().catch(() => {
          clearTimeout(timeout);
          fallbackBrowserTTS(clean, safeResolve);
        });
      } catch {
        clearTimeout(timeout);
        fallbackBrowserTTS(clean, safeResolve);
      }
    });
  }

  async function speakSentenceBySentence(text) {
    const sentences = String(text || "")
      .split(/(?<=[.!?])\s+/)
      .map((s) => s.trim())
      .filter(Boolean);

    for (const sentence of sentences) {
      await speakText(sentence);
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  // ========================================================
  // INVESTIGATION
  // ========================================================

  async function investigate(overrideMessage = null) {
    const override =
      typeof overrideMessage === "string" ? overrideMessage : null;

    const source = override ?? message;
    const trimmed = source.trim();

    if (!trimmed || loading) return null;
    if (override) setMessage(trimmed);

    setLoading(true);
    setError("");
    setData(null);
    setActiveStep(0);
    setShowRawResponse(false);
    setVerificationResult(null);

    const timer = setInterval(() => {
      setActiveStep((current) => {
        if (current >= INVESTIGATION_STEPS.length - 2) {
          return current;
        }
        return current + 1;
      });
    }, 650);

    try {
      const response = await fetch(
        `${API_URL}/ask?message=${encodeURIComponent(trimmed)}`,
      );

      if (!response.ok) {
        let detail = "ORION request failed.";
        try {
          const errorData = await response.json();
          if (errorData?.detail) detail = errorData.detail;
        } catch {}
        throw new Error(detail);
      }

      const result = await response.json();
      setData(result);
      setActiveStep(INVESTIGATION_STEPS.length - 1);

      if (!conversationActive && voiceOutputEnabled) {
        const summary = buildVoiceSummary(result);
        await speakSentenceBySentence(summary);
      }

      return result;
    } catch (requestError) {
      setError(requestError?.message || "Unable to connect to ORION.");
      setData(null);
      return null;
    } finally {
      clearInterval(timer);
      setLoading(false);
    }
  }

  // ========================================================
  // CONVERSATION LOOP
  // ========================================================

  async function startConversation() {
    if (conversationActive) return;

    setConversationActive(true);
    setConversationState("speaking");
    setConversationContext("initial");
    setError("");
    setData(null);
    setVerificationResult(null);
    setLastTranscript(null);

    await speakText(
      "Hi, I'm ORION. I investigate why your computer is running slowly, and I prove my answers with real measurements on your actual machine. What's going on?",
    );

    setConversationState("listening");
  }

  function endConversation() {
    setConversationActive(false);
    setConversationState("idle");
    setConversationContext(null);
    setPendingIntervention(null);
    setLastTranscript(null);

    if (voiceRef.current) {
      try {
        voiceRef.current.stop();
      } catch {}
    }

    speakText(
      "Sounds good. If you need me later, just start a new conversation. Have a great day.",
    ).catch(() => {});
  }

  async function runInvestigationTurn(transcript) {
    setConversationState("speaking");
    setLastTranscript(transcript);

    await speakText(
      "Okay, give me about twenty seconds. I'm going to look at your CPU, memory, disk activity, and running processes. Then I'll investigate anything that looks unusual.",
    );

    setConversationState("investigating");

    const result = await investigate(transcript);

    if (!result) {
      await speakText(
        "Sorry, I couldn't process that. Could you say that again with a bit more detail? For example — 'my laptop is slow' or 'why is Chrome using so much CPU'.",
      );
      setConversationContext("next");
      setConversationState("listening");
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 600));

    setConversationState("speaking");

    const summary = buildVoiceSummary(result);
    await speakSentenceBySentence(summary);

    const strongest = result?.investigation?.strongest_evidence;

    if (isActionable(strongest)) {
      const name = (strongest.process || "").replace(".exe", "");
      await new Promise((resolve) => setTimeout(resolve, 400));
      await speakText(
        `Would you like me to temporarily suspend ${name} and measure the system? You can also say 'why' if you want more detail, or 'show me the data' for the numbers.`,
      );

      setPendingIntervention({
        investigationId: result.investigation_id,
        pid: strongest.pid,
        processName: strongest.process,
      });
      setConversationContext("confirm");
      setConversationState("listening");
    } else {
      await speakText(
        "Based on this investigation, I don't see a clear single cause. You can say 'why' if you want more detail, or tell me what else to investigate.",
      );
      setConversationContext("next");
      setConversationState("listening");
    }
  }

  // ========================================================
  // PRIORITY 4 — FOLLOW-UP HANDLER
  // ========================================================

  async function handleFollowUp(type) {
    if (!data) {
      await speakText(
        "I don't have an investigation to talk about yet. What would you like me to look at?",
      );
      setConversationState("listening");
      return;
    }

    const investigation = data.investigation || {};
    const strongest = investigation.strongest_evidence;
    const evidence = investigation.evidence || [];
    const system = investigation.system || {};
    const diagnosis = data.diagnosis || {};

    setConversationState("speaking");

    if (type === "why") {
      let speech = "";

      if (strongest?.process) {
        const name = strongest.process.replace(".exe", "");
        speech = `Here's my reasoning. The primary signal is ${name}. `;
        speech += `It's currently using ${Math.round(strongest.cpu_percent || 0)} percent CPU. `;
        speech += `Its usage pattern is ${(strongest.temporal_behavior || "unknown").replace(/_/g, " ").toLowerCase()} — meaning `;

        if ((strongest.temporal_behavior || "").includes("PERSISTENT")) {
          speech +=
            "it's not just a quick spike. It's been running this way for a while. ";
        } else if (
          (strongest.temporal_behavior || "").includes("INTERMITTENT")
        ) {
          speech += "it keeps coming and going. ";
        } else if (
          (strongest.temporal_behavior || "").includes("SHORT_SPIKE")
        ) {
          speech +=
            "it was a brief spike, which is why my confidence is limited. ";
        } else {
          speech += "I don't have enough temporal data yet. ";
        }

        speech += `I classified it as a ${(strongest.classification || "candidate").replace(/_/g, " ").toLowerCase()}. `;
        speech += `The evidence score is ${Math.round(strongest.score || 0)} out of one hundred. `;

        if (evidence.length > 1) {
          speech += `I also looked at ${evidence.length - 1} other processes, but they showed less significant patterns. `;
        }
      } else {
        speech =
          "Honestly, I didn't find a clear single candidate in this investigation. ";
      }

      const ram = system.ram_percent;
      const disk = system.disk_status;

      if (ram && ram < 70) {
        speech += `Memory looks fine at ${Math.round(ram)} percent, so that's not the bottleneck. `;
      }
      if (disk === "HEALTHY") {
        speech += `Disk is healthy, so storage isn't the issue. `;
      }

      if (diagnosis.confidence) {
        speech += `Overall, my confidence is ${diagnosis.confidence.toLowerCase()}.`;
      }

      await speakSentenceBySentence(speech);
    } else if (type === "data") {
      let speech = "";

      if (strongest) {
        const name = strongest.process.replace(".exe", "");
        speech = `Here are the numbers. ${name}: `;
        speech += `PID ${strongest.pid}, `;
        speech += `CPU ${Math.round(strongest.cpu_percent || 0)} percent, `;
        speech += `temporal pattern ${(strongest.temporal_behavior || "unknown").replace(/_/g, " ").toLowerCase()}, `;
        speech += `evidence score ${Math.round(strongest.score || 0)} out of one hundred. `;
      }

      if (system.cpu_percent) {
        speech += `System CPU is at ${Math.round(system.cpu_percent)} percent. `;
      }
      if (system.ram_percent) {
        speech += `Memory is at ${Math.round(system.ram_percent)} percent. `;
      }
      if (system.disk_status) {
        speech += `Disk status is ${system.disk_status.toLowerCase()}. `;
      }

      speech += "All of these were measured live on your machine.";

      await speakSentenceBySentence(speech);
    } else if (type === "others") {
      if (evidence.length <= 1) {
        await speakText(
          "There weren't any other significant candidates. Just the one I told you about.",
        );
      } else {
        const others = evidence.slice(1, 4);
        let speech = `The other candidates I found were: `;

        for (let i = 0; i < others.length; i++) {
          const e = others[i];
          const name = (e.process || "unknown").replace(".exe", "");
          speech += `${name}, at ${Math.round(e.cpu_percent || 0)} percent CPU, `;
          speech += `classified as ${(e.classification || "unknown").replace(/_/g, " ").toLowerCase()}. `;
        }

        speech += "None of them scored high enough to warrant action.";
        await speakSentenceBySentence(speech);
      }
    } else if (type === "reset") {
      setData(null);
      setVerificationResult(null);
      setPendingIntervention(null);
      await speakText(
        "Okay, I've cleared that. What would you like me to investigate?",
      );
      setConversationContext("next");
      setConversationState("listening");
      return;
    } else if (type === "investigate_again") {
      if (!lastTranscript) {
        await speakText("I need something to investigate. What's going on?");
        setConversationState("listening");
        return;
      }
      setConversationState("listening");
      await runInvestigationTurn(lastTranscript);
      return;
    }

    await speakText("Would you like me to investigate anything else?");
    setConversationContext("next");
    setConversationState("listening");
  }

  async function runInterventionTurn() {
    if (!pendingIntervention) {
      setConversationState("listening");
      return;
    }

    setConversationState("executing_intervention");

    try {
      const response = await fetch(
        `${API_URL}/investigations/${pendingIntervention.investigationId}/actions/suspend`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved: true,
            pid: pendingIntervention.pid,
            process_name: pendingIntervention.processName,
            suspend_seconds: 4,
          }),
        },
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result?.detail || "Intervention failed.");
      }

      setVerificationResult(result);

      const before = result.measurement?.cpu_before ?? 0;
      const after = result.measurement?.cpu_after ?? 0;
      const status = result.verification?.status ?? "UNKNOWN";

      const improvement = before - after;
      const name = (pendingIntervention.processName || "the process").replace(
        ".exe",
        "",
      );

      let speech = "";

      if (status === "SUPPORTED_BY_INTERVENTION") {
        speech =
          `Okay, the intervention is done. I suspended ${name} for four seconds ` +
          `and measured the system. ` +
          `Your CPU dropped from ${before.toFixed(1)} percent to ${after.toFixed(1)} percent — ` +
          `that's a ${improvement.toFixed(1)} point improvement. ` +
          `${name} has been resumed, so nothing was lost. ` +
          `That's strong evidence that ${name} really was the main cause of the slowdown, ` +
          `not just a symptom. I'm confident about this one. `;
      } else if (status === "WEAK_INTERVENTION_SIGNAL") {
        speech =
          `Alright, the intervention is done. I suspended ${name} for four seconds. ` +
          `Your CPU only dropped from ${before.toFixed(1)} to ${after.toFixed(1)} percent — ` +
          `a small ${improvement.toFixed(1)} point change. ` +
          `${name} has been resumed. ` +
          `Honestly, that's weak evidence. ${name} might be contributing ` +
          `to the problem, but I can't confidently say it's the main cause. ` +
          `There may be something else going on. `;
      } else {
        speech =
          `Here's where it gets interesting. I suspended ${name} for four seconds ` +
          `and measured your system again. ` +
          `Your CPU stayed around ${after.toFixed(1)} percent — no meaningful change. ` +
          `${name} has been resumed. ` +
          `That means I was wrong about ${name} being the primary cause. ` +
          `It looked like a strong candidate, but the measurement proved it wasn't. ` +
          `This is exactly why I don't just guess — I test my answers. ` +
          `The real cause must be something else. `;
      }

      setConversationState("speaking");
      await speakSentenceBySentence(speech);

      if (status === "SUPPORTED_BY_INTERVENTION") {
        await speakText("Would you like me to investigate anything else?");
      } else if (status === "WEAK_INTERVENTION_SIGNAL") {
        await speakText(
          "Would you like me to look at the other candidates, or investigate something else entirely?",
        );
      } else {
        await speakText(
          "Would you like me to investigate further and try to find the real cause?",
        );
      }

      setPendingIntervention(null);
      setConversationContext("next");
      setConversationState("listening");
    } catch (err) {
      console.error("Intervention failed:", err);
      await speakText(
        "The intervention failed. Would you like to try something else?",
      );
      setPendingIntervention(null);
      setConversationContext("next");
      setConversationState("listening");
    }
  }

  async function handleConversationTranscript(transcript) {
    const cleaned = (transcript || "").trim();
    if (!cleaned) return;

    // Small talk first
    const smallTalk = parseSmallTalk(cleaned);
    if (smallTalk) {
      setConversationState("speaking");
      await speakText(smallTalk.speech);

      if (smallTalk.endConversation) {
        endConversation();
        return;
      }

      if (conversationContext === "confirm") {
        setConversationState("listening");
        return;
      }

      setConversationContext("next");
      setConversationState("listening");
      return;
    }

    // PRIORITY 4 — Follow-up commands (only if we have investigation data)
    if (
      data &&
      (conversationContext === "confirm" || conversationContext === "next")
    ) {
      const followUp = parseFollowUp(cleaned);
      if (followUp) {
        await handleFollowUp(followUp);
        return;
      }
    }

    if (conversationContext === "confirm") {
      const answer = parseYesNo(cleaned);

      if (answer === "yes") {
        await runInterventionTurn();
      } else if (answer === "no") {
        await speakText(
          "Okay, I won't take any action. Would you like me to investigate anything else?",
        );
        setPendingIntervention(null);
        setConversationContext("next");
        setConversationState("listening");
      } else {
        await speakText(
          "I didn't catch that. Please say yes or no. You can also say 'why' for more detail, or 'show me the data'.",
        );
        setConversationState("listening");
      }
      return;
    }

    if (conversationContext === "next") {
      if (parseDone(cleaned)) {
        endConversation();
        return;
      }
      await runInvestigationTurn(cleaned);
      return;
    }

    await runInvestigationTurn(cleaned);
  }

  function handleVoiceTranscript(transcript) {
    const cleaned = (transcript || "").trim();
    if (!cleaned) return;

    if (conversationActive) {
      handleConversationTranscript(cleaned);
      return;
    }

    investigate(cleaned);
  }

  useEffect(() => {
    if (!conversationActive) return;
    if (conversationState !== "listening") return;

    const timer = setTimeout(() => {
      if (voiceRef.current) {
        try {
          voiceRef.current.start();
        } catch {}
      }
    }, 700);

    return () => clearTimeout(timer);
  }, [conversationActive, conversationState]);

  // ========================================================
  // LOAD PREVIOUS INVESTIGATION
  // ========================================================

  async function loadInvestigation(investigationId) {
    if (!investigationId || loading) return;

    try {
      setError("");
      setShowRawResponse(false);

      const response = await fetch(
        `${API_URL}/investigations/${encodeURIComponent(investigationId)}`,
      );

      if (!response.ok) {
        let detail = "Unable to load investigation.";
        try {
          const errorData = await response.json();
          if (errorData?.detail) detail = errorData.detail;
        } catch {}
        throw new Error(detail);
      }

      const result = await response.json();

      if (result?.investigation) {
        setData(result.investigation);
        if (result.investigation.question) {
          setMessage(result.investigation.question);
        }
      } else {
        throw new Error("Stored investigation has an invalid format.");
      }

      setActiveStep(INVESTIGATION_STEPS.length - 1);
    } catch (requestError) {
      setError(requestError?.message || "Unable to load investigation.");
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      investigate();
    }
  }

  // ========================================================
  // STRUCTURED DATA
  // ========================================================

  const investigation = data?.investigation || {};
  const system = investigation.system || {};
  const stages = investigation.stages || {};
  const strongestEvidence = investigation.strongest_evidence;
  const rootCauses = investigation.root_causes || [];
  const evidence = investigation.evidence || [];
  const rootCauseStatus = investigation.root_cause_status || "UNCONFIRMED";

  const systemCards = useMemo(() => {
    return [
      {
        label: "CPU",
        value:
          system.cpu_percent !== null && system.cpu_percent !== undefined
            ? `${formatNumber(system.cpu_percent)}%`
            : "—",
        description: "Current system load",
      },
      {
        label: "RAM",
        value:
          system.ram_percent !== null && system.ram_percent !== undefined
            ? `${formatNumber(system.ram_percent)}%`
            : "—",
        description: "Memory utilization",
      },
      {
        label: "DISK",
        value: formatStatus(system.disk_status),
        description: "Storage condition",
      },
      {
        label: "GPU",
        value: formatStatus(system.gpu_status),
        description: "Graphics activity",
      },
    ];
  }, [system]);

  // ========================================================
  // PRIORITY 3 — REASONING ANALYSIS
  // ========================================================

  const reasoning = useMemo(() => {
    if (!data || !strongestEvidence) return null;

    const signals = [];
    if (strongestEvidence.cpu_percent !== undefined) {
      signals.push({
        label: "CPU",
        value: `${Math.round(strongestEvidence.cpu_percent)}%`,
      });
    }
    if (strongestEvidence.temporal_behavior) {
      signals.push({
        label: "Temporal",
        value: formatStatus(strongestEvidence.temporal_behavior),
      });
    }
    if (strongestEvidence.classification) {
      signals.push({
        label: "Classification",
        value: formatClassification(strongestEvidence.classification),
      });
    }
    if (strongestEvidence.score !== undefined) {
      signals.push({
        label: "Evidence score",
        value: `${strongestEvidence.score} / 100`,
      });
    }
    if (strongestEvidence.confidence) {
      signals.push({
        label: "Confidence",
        value: formatStatus(strongestEvidence.confidence),
      });
    }

    const ruledOut = [];
    const ram = system.ram_percent;
    if (ram !== null && ram !== undefined && ram < 75) {
      ruledOut.push(
        `Memory pressure — RAM at ${Math.round(ram)}%, within normal range`,
      );
    }
    if (system.disk_status === "HEALTHY") {
      ruledOut.push("Storage latency — disk marked HEALTHY");
    }
    if (
      system.gpu_status === "IDLE" ||
      system.gpu_status === "LOW" ||
      system.gpu_status === "INACTIVE"
    ) {
      ruledOut.push("GPU bottleneck — GPU activity is low");
    }
    if (rootCauseStatus === "STRONG_PROCESS_CANDIDATE") {
      ruledOut.push("System-level causes — process-level evidence dominates");
    }

    let narrative = "";
    if (strongestEvidence.process) {
      const name = strongestEvidence.process.replace(".exe", "");
      narrative += `ORION identified ${name} as the strongest candidate based on `;
      narrative += `${strongestEvidence.cpu_percent ? "elevated CPU usage" : "observed signals"}`;
      if (strongestEvidence.temporal_behavior) {
        narrative += `, a ${String(strongestEvidence.temporal_behavior).replace(/_/g, " ").toLowerCase()} usage pattern`;
      }
      if (strongestEvidence.classification) {
        narrative += `, and an overall classification of ${String(strongestEvidence.classification).replace(/_/g, " ").toLowerCase()}`;
      }
      narrative += ". ";
    }
    if (ruledOut.length > 0) {
      narrative +=
        "Other subsystems were checked and ruled out as primary causes.";
    }

    return { signals, ruledOut, narrative };
  }, [data, strongestEvidence, system, rootCauseStatus]);

  function getPipelineStatus(stepKey, index) {
    if (!loading && data) return "complete";
    if (index < activeStep) return "complete";
    if (index === activeStep && loading) return "active";
    return "pending";
  }

  const timelineStep = loading ? "investigate" : data ? "diagnose" : "observe";

  // ========================================================
  // RENDER
  // ========================================================

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">O</div>
          <div>
            <div className="brand-name">ORION</div>
            <div className="brand-subtitle">FIELD INTELLIGENCE</div>
          </div>
        </div>

        <div className="system-status">
          <button
            type="button"
            className="voice-toggle"
            onClick={() => {
              setVoiceOutputEnabled((v) => !v);
              if (audioRef.current) {
                try {
                  audioRef.current.pause();
                } catch {}
              }
            }}
            title={
              voiceOutputEnabled ? "Mute ORION voice" : "Unmute ORION voice"
            }
          >
            {voiceOutputEnabled ? "🔊" : "🔇"}
          </button>
          <span className="status-dot" />
          SYSTEM ONLINE
        </div>
      </header>

      <main className="page">
        <section className="hero">
          <div className="eyebrow">EVIDENCE-BASED COMPUTER INTELLIGENCE</div>
          <h1>
            Investigate your machine.
            <br />
            Understand the cause.
          </h1>
          <p>
            ORION observes system behavior, investigates anomalies, ranks
            possible causes, and produces an evidence-based diagnosis.
          </p>
        </section>

        <section className="panel request-panel">
          <div className="panel-label">INVESTIGATION REQUEST</div>

          <div className="request-row">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Describe what is happening..."
              disabled={loading}
            />

            <button
              className="investigate-button"
              onClick={investigate}
              disabled={loading || !message.trim()}
            >
              {loading ? "INVESTIGATING..." : "INVESTIGATE →"}
            </button>
          </div>

          <div className="input-hint">Press Enter to investigate</div>
        </section>

        <section className="panel conversation-panel">
          <div className="panel-label">VOICE CONVERSATION</div>

          <div className="conversation-header">
            <div>
              <h2>Talk with ORION</h2>
              <div className="conversation-subtitle">
                A two-way voice agent — speak, ORION investigates, ORION speaks
                back
              </div>
            </div>
            <div className="conversation-status">
              {conversationActive ? conversationState.toUpperCase() : "READY"}
            </div>
          </div>

          <div className="conversation-controls">
            {!conversationActive ? (
              <button
                type="button"
                className="conversation-button"
                onClick={startConversation}
                disabled={loading}
              >
                🎙 START CONVERSATION
              </button>
            ) : (
              <button
                type="button"
                className="conversation-button stop"
                onClick={endConversation}
              >
                ■ END CONVERSATION
              </button>
            )}
          </div>

          {conversationActive && (
            <>
              <div className="conversation-hint">
                {conversationState === "listening" &&
                  "🎤 Listening (or type below)..."}
                {conversationState === "investigating" && "🔍 Investigating..."}
                {conversationState === "speaking" && "🔊 ORION is speaking..."}
                {conversationState === "executing_intervention" &&
                  "⚙️ Executing intervention..."}
              </div>

              <div className="conversation-typed-row">
                <input
                  type="text"
                  className="conversation-typed-input"
                  placeholder="Or type your reply and press Enter..."
                  disabled={
                    conversationState === "investigating" ||
                    conversationState === "executing_intervention" ||
                    conversationState === "speaking"
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      const value = event.currentTarget.value.trim();
                      if (value) {
                        handleConversationTranscript(value);
                        event.currentTarget.value = "";
                      }
                    }
                  }}
                />
              </div>
            </>
          )}
        </section>

        <VoiceInput
          ref={voiceRef}
          onTranscript={handleVoiceTranscript}
          disabled={loading}
          autoStopOnFinal={conversationActive}
          hideControls={conversationActive}
        />

        {error && (
          <section className="error-panel">
            <strong>ORION CONNECTION ERROR</strong>
            <span>{error}</span>
          </section>
        )}

        <InvestigationTimeline activeStep={timelineStep} />

        <section className="panel">
          <div className="panel-label">INVESTIGATION PIPELINE</div>

          <div className="pipeline-header">
            <div>
              <h2>
                {data
                  ? "Investigation complete"
                  : loading
                    ? "Investigation in progress"
                    : "Ready to investigate"}
              </h2>
            </div>
            {data && <div className="complete-badge">COMPLETE</div>}
          </div>

          <div className="pipeline">
            {INVESTIGATION_STEPS.map(([key, label], index) => {
              const status = getPipelineStatus(key, index);
              const backendStatus = stages[key];

              return (
                <div className={`pipeline-step ${status}`} key={key}>
                  <div className="step-icon">
                    {status === "complete"
                      ? "✓"
                      : status === "active"
                        ? "●"
                        : "○"}
                  </div>
                  <div className="step-content">
                    <div className="step-label">{label}</div>
                    {data && backendStatus && (
                      <div className="step-status">
                        {formatStatus(backendStatus)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {data && (
          <section className="panel">
            <div className="panel-label">TELEMETRY</div>
            <div className="section-heading-row">
              <div>
                <h2>System health</h2>
              </div>
              <div className="observed-badge">● OBSERVED</div>
            </div>
            <div className="health-grid">
              {systemCards.map((card) => (
                <div className="health-card" key={card.label}>
                  <div className="health-label">{card.label}</div>
                  <div className="health-value">{card.value}</div>
                  <div className="health-description">{card.description}</div>
                </div>
              ))}
            </div>
          </section>
        )}

        {data && (
          <section className="panel">
            <div className="panel-label">EVIDENCE FUSION</div>

            <div className="section-heading-row">
              <div>
                <h2>Strongest evidence</h2>
              </div>
              {strongestEvidence?.score !== null &&
                strongestEvidence?.score !== undefined && (
                  <div className="score-badge">
                    SCORE {strongestEvidence.score}
                  </div>
                )}
            </div>

            {strongestEvidence ? (
              <div className="evidence-card">
                <div className="evidence-main">
                  <div className="evidence-icon">⬡</div>
                  <div>
                    <div className="evidence-kicker">PRIMARY PROCESS</div>
                    <div className="evidence-process">
                      {strongestEvidence.process || "Process not identified"}
                    </div>
                  </div>
                </div>

                <div className="evidence-metrics">
                  <div className="metric">
                    <span>PID</span>
                    <strong>{strongestEvidence.pid ?? "N/A"}</strong>
                  </div>
                  <div className="metric">
                    <span>CPU</span>
                    <strong>
                      {strongestEvidence.cpu_percent !== null &&
                      strongestEvidence.cpu_percent !== undefined
                        ? `${formatNumber(strongestEvidence.cpu_percent)}%`
                        : strongestEvidence.cpu_range
                          ? `${formatNumber(
                              strongestEvidence.cpu_range.min,
                            )}–${formatNumber(
                              strongestEvidence.cpu_range.max,
                            )}%`
                          : "N/A"}
                    </strong>
                  </div>
                  <div className="metric">
                    <span>TEMPORAL BEHAVIOR</span>
                    <strong>
                      {formatStatus(strongestEvidence.temporal_behavior)}
                    </strong>
                  </div>
                  <div className="metric">
                    <span>EVIDENCE SCORE</span>
                    <strong>{strongestEvidence.score ?? "N/A"}</strong>
                  </div>
                  <div className="metric">
                    <span>CLASSIFICATION</span>
                    <strong>
                      {formatClassification(strongestEvidence.classification)}
                    </strong>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-evidence">
                No strong evidence was identified from the current
                investigation.
              </div>
            )}

            {evidence.length > 1 && (
              <div className="evidence-list">
                <div className="subsection-title">Supporting evidence</div>
                {evidence.map((item, index) => (
                  <div
                    className="evidence-row"
                    key={`${item.process}-${item.pid}-${index}`}
                  >
                    <div>
                      <strong>{item.process || "System signal"}</strong>
                      <span>
                        {item.pids && item.pids.length > 0
                          ? `PIDs ${item.pids.join(", ")}`
                          : item.pid !== null && item.pid !== undefined
                            ? `PID ${item.pid}`
                            : "PID unavailable"}
                      </span>
                    </div>
                    <div>
                      {item.cpu_percent !== null &&
                      item.cpu_percent !== undefined
                        ? `${formatNumber(item.cpu_percent)}% CPU`
                        : item.cpu_range
                          ? `${formatNumber(item.cpu_range.min)}–${formatNumber(
                              item.cpu_range.max,
                            )}% CPU`
                          : "CPU N/A"}
                    </div>
                    <div>{formatStatus(item.temporal_behavior)}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* ==================================================
            PRIORITY 3 — ORION REASONING
        ================================================== */}

        {data && reasoning && (
          <section className="panel reasoning-panel">
            <div className="panel-label">ORION REASONING</div>

            <div className="section-heading-row">
              <div>
                <h2>Why this conclusion</h2>
              </div>
              <div className="observed-badge">● ANALYZED</div>
            </div>

            <div className="reasoning-grid">
              <div className="reasoning-section">
                <h3>PRIMARY SIGNALS</h3>
                {reasoning.signals.map((s, i) => (
                  <div className="reasoning-signal" key={i}>
                    <span>{s.label}</span>
                    <strong>{s.value}</strong>
                  </div>
                ))}
              </div>

              <div className="reasoning-section">
                <h3>RULED OUT</h3>
                {reasoning.ruledOut.length > 0 ? (
                  <ul className="reasoning-ruled">
                    {reasoning.ruledOut.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ opacity: 0.6, fontSize: "13px" }}>
                    No subsystems could be definitively ruled out.
                  </p>
                )}
              </div>

              {reasoning.narrative && (
                <div className="reasoning-text">{reasoning.narrative}</div>
              )}
            </div>
          </section>
        )}

        {data && (
          <section className="panel">
            <div className="panel-label">ROOT CAUSE ANALYSIS</div>
            <div className="section-heading-row">
              <h2>Likely causes</h2>
              <div className={`cause-status ${rootCauseStatus.toLowerCase()}`}>
                {formatStatus(rootCauseStatus)}
              </div>
            </div>

            {rootCauses.length > 0 ? (
              <div className="cause-list">
                {rootCauses.map((cause, index) => (
                  <div className="cause-card" key={`${cause.name}-${index}`}>
                    <div className="cause-number">
                      {String(index + 1).padStart(2, "0")}
                    </div>
                    <div className="cause-content">
                      <div className="cause-name">{cause.name}</div>
                      <div className="cause-meta">
                        <span>CONFIDENCE</span>
                        <strong>{formatStatus(cause.confidence)}</strong>
                        {cause.score !== null && cause.score !== undefined && (
                          <>
                            <span>SCORE</span>
                            <strong>{cause.score}</strong>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-evidence">
                ORION did not identify a specific root cause.
              </div>
            )}
          </section>
        )}

        {data && (
          <section className="panel">
            <div className="panel-label">ORION DIAGNOSIS</div>
            <div className="diagnosis-heading">
              <h2>What ORION found</h2>
            </div>

            <div className="diagnosis-grid">
              <article>
                <h3>OBSERVATION</h3>
                <p>
                  {data.diagnosis?.observation || "No observation available."}
                </p>
              </article>
              <article>
                <h3>EVIDENCE</h3>
                <p>
                  {data.diagnosis?.evidence || "No evidence summary available."}
                </p>
              </article>
              <article>
                <h3>CONFIDENCE</h3>
                <div className="confidence-value">
                  {formatStatus(data.diagnosis?.confidence)}
                </div>
                <p>Based on the evidence collected during the investigation.</p>
              </article>
              <article>
                <h3>NEXT STEP</h3>
                <p>{data.diagnosis?.next_step || "No next step available."}</p>
              </article>
            </div>

            <div className="causes-summary">
              <h3>LIKELY CAUSES</h3>
              <p>
                {data.diagnosis?.likely_causes ||
                  "No specific cause confirmed."}
              </p>
            </div>
          </section>
        )}

        {data && (
          <ActionPanel
            investigationId={data?.investigation_id}
            evidence={strongestEvidence}
            onComplete={setVerificationResult}
          />
        )}

        <VerificationResult result={verificationResult} />

        <InvestigationHistory onSelect={loadInvestigation} />

        {data && (
          <section className="raw-section">
            <button
              className="raw-toggle"
              onClick={() => setShowRawResponse((current) => !current)}
            >
              {showRawResponse
                ? "Hide complete ORION response"
                : "View complete ORION response"}
            </button>
            {showRawResponse && (
              <pre className="raw-response">{data.response}</pre>
            )}
          </section>
        )}
      </main>

      <footer className="footer">
        ORION FIELD INTELLIGENCE
        <span>Evidence-based computer investigation</span>
      </footer>
    </div>
  );
}

export default App;
