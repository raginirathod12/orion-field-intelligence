import { useMemo, useState } from "react";
import "./App.css";
import InvestigationTimeline from "./InvestigationTimeline";
import ActionPanel from "./ActionPanel";
import VerificationResult from "./VerificationResult";
import InvestigationHistory from "./InvestigationHistory";
import VoiceInput from "./VoiceInput"; // ← CHANGED (new import)
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

function App() {
  const [message, setMessage] = useState(DEFAULT_MESSAGE);

  const [data, setData] = useState(null);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const [activeStep, setActiveStep] = useState(-1);

  const [showRawResponse, setShowRawResponse] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);

  // ========================================================
  // INVESTIGATION REQUEST
  // ========================================================
  async function investigate(overrideMessage = null) {
    // If called from a click handler, the first arg is the event — ignore it.
    const override =
      typeof overrideMessage === "string" ? overrideMessage : null;

    const source = override ?? message;
    const trimmed = source.trim();
    if (!trimmed || loading) {
      return;
    }
    if (override) {
      setMessage(trimmed);
    }

    setLoading(true);
    setError("");
    setData(null);
    setActiveStep(0);
    setShowRawResponse(false);
    setVerificationResult(null);

    const timer = setInterval(() => {
      setActiveStep((current) => {
        // Stop at the second-to-last step.
        // The last step ("Generating diagnosis") only
        // completes when the backend actually responds.
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

          if (errorData?.detail) {
            detail = errorData.detail;
          }
        } catch {
          // Ignore JSON parsing errors.
        }

        throw new Error(detail);
      }

      const result = await response.json();

      setData(result);

      setActiveStep(INVESTIGATION_STEPS.length - 1);
    } catch (requestError) {
      setError(requestError?.message || "Unable to connect to ORION.");

      setData(null);
    } finally {
      clearInterval(timer);

      setLoading(false);
    }
  }

  // ========================================================
  // VOICE TRANSCRIPT HANDLER  ← CHANGED (new function)
  // ========================================================
  function handleVoiceTranscript(transcript) {
    const cleaned = (transcript || "").trim();
    if (!cleaned) {
      return;
    }
    investigate(cleaned);
  }

  // ========================================================
  // LOAD PREVIOUS INVESTIGATION
  // ========================================================

  async function loadInvestigation(investigationId) {
    if (!investigationId || loading) {
      return;
    }

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

          if (errorData?.detail) {
            detail = errorData.detail;
          }
        } catch {
          // Ignore JSON parsing errors.
        }

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

  // ========================================================
  // ENTER KEY
  // ========================================================

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

  // ========================================================
  // ROOT CAUSE STATUS
  // ========================================================

  const rootCauseStatus = investigation.root_cause_status || "UNCONFIRMED";

  // ========================================================
  // SYSTEM HEALTH
  // ========================================================

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
  // PIPELINE STATUS
  // ========================================================

  function getPipelineStatus(stepKey, index) {
    if (!loading && data) {
      return "complete";
    }

    if (index < activeStep) {
      return "complete";
    }

    if (index === activeStep && loading) {
      return "active";
    }

    return "pending";
  }

  // ========================================================
  // TIMELINE ACTIVE STEP
  // ========================================================

  const timelineStep = loading ? "investigate" : data ? "diagnose" : "observe";

  // ========================================================
  // RENDER
  // ========================================================

  return (
    <div className="app-shell">
      {/* ==================================================
          HEADER
      ================================================== */}

      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">O</div>

          <div>
            <div className="brand-name">ORION</div>

            <div className="brand-subtitle">FIELD INTELLIGENCE</div>
          </div>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          SYSTEM ONLINE
        </div>
      </header>

      {/* ==================================================
          HERO
      ================================================== */}

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

        {/* ==================================================
            REQUEST
        ================================================== */}

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

        {/* ==================================================
            VOICE INPUT  ← CHANGED (new component)
        ================================================== */}

        <VoiceInput onTranscript={handleVoiceTranscript} disabled={loading} />

        {/* ==================================================
            ERROR
        ================================================== */}

        {error && (
          <section className="error-panel">
            <strong>ORION CONNECTION ERROR</strong>

            <span>{error}</span>
          </section>
        )}

        {/* ==================================================
            NEW INVESTIGATION TIMELINE
        ================================================== */}

        <InvestigationTimeline activeStep={timelineStep} />

        {/* ==================================================
            PIPELINE
        ================================================== */}

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

        {/* ==================================================
            TELEMETRY
        ================================================== */}

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

        {/* ==================================================
            EVIDENCE FUSION
        ================================================== */}

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

            {/* ==================================================
                ALL EVIDENCE
            ================================================== */}

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
            ROOT CAUSE ANALYSIS
        ================================================== */}

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

        {/* ==================================================
            DIAGNOSIS
        ================================================== */}

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

        {/* ==================================================
            CONTROLLED INTERVENTION
        ================================================== */}

        {data && (
          <ActionPanel
            investigationId={data?.investigation_id}
            evidence={strongestEvidence}
            onComplete={setVerificationResult}
          />
        )}

        <VerificationResult result={verificationResult} />

        {/* ==================================================
            INVESTIGATION HISTORY
        ================================================== */}

        <InvestigationHistory onSelect={loadInvestigation} />

        {/* ==================================================
            RAW RESPONSE
        ================================================== */}

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

      {/* ==================================================
          FOOTER
      ================================================== */}

      <footer className="footer">
        ORION FIELD INTELLIGENCE
        <span>Evidence-based computer investigation</span>
      </footer>
    </div>
  );
}

export default App;
