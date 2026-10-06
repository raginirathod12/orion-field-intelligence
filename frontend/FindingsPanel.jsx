import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

function formatRelativeTime(iso) {
  if (!iso) return "";

  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const seconds = Math.floor((now - then) / 1000);

    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  } catch {
    return "";
  }
}

export default function FindingsPanel() {
  const [findings, setFindings] = useState([]);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadFindings() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_URL}/findings?limit=5`);
      if (!response.ok) {
        throw new Error("Unable to load findings.");
      }

      const data = await response.json();
      setFindings(data.findings || []);
      setMeta({
        enabled: data.watcher_enabled,
        interval: data.interval_seconds,
        cpu: data.cpu_threshold,
        ram: data.ram_threshold,
      });
    } catch (err) {
      setError(err?.message || "Failed to load findings.");
    } finally {
      setLoading(false);
    }
  }

  async function checkNow() {
    try {
      setLoading(true);
      await fetch(`${API_URL}/findings/check-now`, { method: "POST" });
      await loadFindings();
    } catch (err) {
      setError(err?.message || "Failed.");
    } finally {
      setLoading(false);
    }
  }

  async function clearFindings() {
    if (!window.confirm("Clear all findings?")) return;
    try {
      await fetch(`${API_URL}/findings/clear`, { method: "POST" });
      await loadFindings();
    } catch (err) {
      setError(err?.message || "Failed.");
    }
  }

  useEffect(() => {
    loadFindings();
    const timer = setInterval(loadFindings, 10000);
    return () => clearInterval(timer);
  }, []);

  const severityClass = (sev) => {
    const s = String(sev || "").toUpperCase();
    if (s === "CRITICAL") return "finding-critical";
    if (s === "WARNING") return "finding-warning";
    return "finding-info";
  };

  return (
    <section className="panel findings-panel">
      <div className="panel-label">RECENT FINDINGS</div>

      <div className="section-heading-row">
        <div>
          <h2>Automatic monitoring</h2>
          <div className="findings-subtitle">
            {meta?.enabled
              ? `Watching every ${meta.interval}s · CPU ≥ ${meta.cpu}% · RAM ≥ ${meta.ram}%`
              : "Watcher disabled"}
          </div>
        </div>
        <div className="findings-controls">
          <button
            type="button"
            className="findings-button"
            onClick={checkNow}
            disabled={loading}
          >
            CHECK NOW
          </button>
          <button
            type="button"
            className="findings-button secondary"
            onClick={clearFindings}
            disabled={loading || findings.length === 0}
          >
            CLEAR
          </button>
        </div>
      </div>

      {error && <div className="findings-error">{error}</div>}

      {findings.length === 0 ? (
        <div className="findings-empty">
          No findings yet. System looks healthy.
          <br />
          Start a CPU load script and wait ~30 seconds.
        </div>
      ) : (
        <div className="findings-list">
          {findings.map((f) => (
            <div
              key={f.finding_id}
              className={`finding-row ${severityClass(f.severity)}`}
            >
              <div className="finding-head">
                <span className="finding-severity">{f.severity}</span>
                <span className="finding-time">
                  {formatRelativeTime(f.created_at)}
                </span>
              </div>
              <div className="finding-title">{f.title}</div>
              {f.summary && <div className="finding-summary">{f.summary}</div>}
              {f.investigation_id && (
                <div className="finding-link">
                  Investigation: {f.investigation_id}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
