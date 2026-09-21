function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }

  return Number(value).toFixed(1);
}

function formatStatus(value) {
  if (!value) {
    return "UNKNOWN";
  }

  return String(value).replaceAll("_", " ").toUpperCase();
}

export default function VerificationResult({ result }) {
  if (!result) {
    return null;
  }

  const measurement = result.measurement || {};

  const verification = result.verification || {};

  const intervention = result.intervention || {};

  const before = measurement.cpu_before;
  const after = measurement.cpu_after;
  const improvement = measurement.cpu_improvement;

  const verified = verification.status === "SUPPORTED_BY_INTERVENTION";

  return (
    <section className="panel verification-panel">
      <div className="panel-label">INTERVENTION VERIFICATION</div>

      <div className="verification-header">
        <div>
          <h2>{verified ? "Intervention supported" : "Intervention result"}</h2>

          <div className="verification-subtitle">
            {result.process_name} • PID {result.pid}
          </div>
        </div>

        <div
          className={
            verified ? "verification-status verified" : "verification-status"
          }
        >
          {formatStatus(verification.status)}
        </div>
      </div>

      <div className="verification-metrics">
        <div className="verification-metric">
          <span>CPU BEFORE</span>
          <strong>{formatNumber(before)}%</strong>
        </div>

        <div className="verification-arrow">→</div>

        <div className="verification-metric">
          <span>CPU AFTER</span>
          <strong>{formatNumber(after)}%</strong>
        </div>

        <div className="verification-metric">
          <span>IMPROVEMENT</span>
          <strong>
            {formatNumber(improvement)}
            <small> pts</small>
          </strong>
        </div>
      </div>

      <div className="verification-details">
        <div>
          <span>Action</span>
          <strong>Temporarily suspended</strong>
        </div>

        <div>
          <span>Duration</span>
          <strong>{formatNumber(intervention.suspend_seconds)} sec</strong>
        </div>

        <div>
          <span>Process resumed</span>
          <strong>{intervention.resumed ? "YES" : "NO / EXITED"}</strong>
        </div>
      </div>

      <div className="verification-evidence">
        <div className="verification-evidence-title">VERIFICATION EVIDENCE</div>

        <p>
          {verification.evidence || "No verification evidence was returned."}
        </p>
      </div>
    </section>
  );
}
