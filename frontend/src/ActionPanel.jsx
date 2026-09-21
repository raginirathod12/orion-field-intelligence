import { useState } from "react";

const API_URL = "http://127.0.0.1:8000";

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

export default function ActionPanel({ investigationId, evidence, onComplete }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  if (!investigationId || !evidence) {
    return null;
  }

  const pid =
    evidence.pid ??
    (evidence.pids && evidence.pids.length > 0 ? evidence.pids[0] : null);

  const processName = evidence.process || evidence.process_name || "";

  if (!pid || !processName) {
    return null;
  }

  const isProtected = PROTECTED_NAMES.has(processName.toLowerCase());

  // =========================================================
  // ACTIONABILITY GATE
  // =========================================================
  const classification = (evidence.classification || "").toUpperCase();
  const score = Number(evidence.score ?? 0);
  const confidence = (evidence.confidence || "").toUpperCase();

  const isNotActionable =
    classification === "WEAKENED" ||
    classification === "UNSUPPORTED" ||
    classification === "NOT_CONFIRMED" ||
    score <= 0 ||
    confidence === "LOW";

  if (isNotActionable && !isProtected) {
    return (
      <section className="panel action-panel">
        <div className="panel-label">ORION ACTION</div>
        <h2>Controlled intervention</h2>
        <div className="action-target">
          <strong>{processName}</strong>
          <span>PID {pid}</span>
        </div>
        <div className="action-protected">
          <strong>NOT ACTIONABLE</strong>
          <p>
            ORION classified this candidate as {classification || "unsupported"}{" "}
            with score {score} and {confidence || "unknown"} confidence. A
            controlled intervention is not justified. Continue investigating
            before acting.
          </p>
        </div>
      </section>
    );
  }

  // =========================================================
  // INTERVENTION
  // =========================================================
  async function handleIntervention() {
    const confirmed = window.confirm(
      `Temporarily suspend ${processName} (PID ${pid}) and measure system CPU? ORION will automatically attempt to resume it after the test.`,
    );

    if (!confirmed) {
      return;
    }

    try {
      setLoading(true);
      setError("");
      setResult(null);

      const response = await fetch(
        `${API_URL}/investigations/${investigationId}/actions/suspend`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            approved: true,
            pid,
            process_name: processName,
            suspend_seconds: 4,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "Intervention failed.");
      }

      setResult(data);

      if (onComplete) {
        onComplete(data);
      }
    } catch (requestError) {
      console.error("ORION remediation error:", requestError);
      setError(requestError?.message || "Unable to complete intervention.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel action-panel">
      <div className="panel-label">ORION ACTION</div>

      <h2>Controlled intervention</h2>

      <div className="action-target">
        <strong>{processName}</strong>
        <span>PID {pid}</span>
      </div>

      {isProtected ? (
        <div className="action-protected">
          <strong>PROTECTED PROCESS</strong>
          <p>
            ORION will not suspend this Windows system process. Additional
            investigation is required.
          </p>
        </div>
      ) : !result ? (
        <>
          <p className="action-description">
            ORION can temporarily suspend this investigated process, measure
            system behavior, and resume it automatically.
          </p>

          <button
            type="button"
            className="action-button"
            onClick={handleIntervention}
            disabled={loading}
          >
            {loading
              ? "RUNNING INTERVENTION..."
              : "TEMPORARILY SUSPEND & VERIFY"}
          </button>
        </>
      ) : (
        <div className="action-result">
          <div className="action-result-status">
            {result?.verification?.status || "UNKNOWN"}
          </div>

          <div className="action-metrics">
            <div>
              <span>CPU BEFORE</span>
              <strong>{result?.measurement?.cpu_before ?? "—"}%</strong>
            </div>

            <div>
              <span>CPU DURING</span>
              <strong>{result?.measurement?.cpu_after ?? "—"}%</strong>
            </div>

            <div>
              <span>IMPROVEMENT</span>
              <strong>{result?.measurement?.cpu_improvement ?? "—"}%</strong>
            </div>
          </div>

          <div className="action-resume">
            {result?.intervention?.resumed
              ? "✓ PROCESS RESUMED"
              : "⚠ PROCESS RESUME NOT CONFIRMED"}
          </div>

          <p>{result?.verification?.evidence}</p>
        </div>
      )}

      {error && <div className="action-error">{error}</div>}
    </section>
  );
}
