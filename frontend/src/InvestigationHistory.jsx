import { useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

function formatStatus(value) {
  if (value === null || value === undefined || value === "") {
    return "UNKNOWN";
  }

  return String(value).replaceAll("_", " ").toUpperCase();
}

export default function InvestigationHistory({ onSelect }) {
  const [items, setItems] = useState([]);

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  async function loadHistory() {
    try {
      setLoading(true);

      setError("");

      const response = await fetch(`${API_URL}/investigations?limit=10`);

      if (!response.ok) {
        throw new Error("Unable to load investigation history.");
      }

      const result = await response.json();

      setItems(result?.investigations || []);
    } catch (requestError) {
      console.error("Investigation history error:", requestError);

      setError(requestError?.message || "Unable to load history.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  return (
    <section className="panel investigation-history">
      <div className="panel-label">INVESTIGATION HISTORY</div>

      <div className="history-header">
        <div>
          <h2>Previous investigations</h2>

          <div className="history-subtitle">Stored ORION investigations</div>
        </div>

        <button
          type="button"
          className="history-refresh"
          onClick={loadHistory}
          disabled={loading}
        >
          {loading ? "LOADING..." : "REFRESH"}
        </button>
      </div>

      {error && <div className="history-error">{error}</div>}

      {!loading && !error && items.length === 0 && (
        <div className="history-empty">No investigations recorded yet.</div>
      )}

      {items.length > 0 && (
        <div className="history-list">
          {items.map((item) => (
            <button
              type="button"
              className="history-item"
              key={item.investigation_id}
              onClick={() => onSelect?.(item.investigation_id)}
            >
              <div className="history-item-top">
                <span className="history-id">{item.investigation_id}</span>

                <span className="history-status">
                  {formatStatus(item.status)}
                </span>
              </div>

              <div className="history-question">{item.question}</div>

              <div className="history-meta">
                <span>{item.intent || "GENERAL"}</span>

                <span>•</span>

                <span>
                  {item.created_at
                    ? new Date(item.created_at).toLocaleString()
                    : "Unknown time"}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
