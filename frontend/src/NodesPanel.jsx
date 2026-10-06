import React, { useState, useEffect } from "react";

const API_URL = "http://127.0.0.1:8000";

const NodesPanel = () => {
    const [nodes, setNodes] = useState([]);

    useEffect(() => {
        const load = async () => {
            try {
                const response = await fetch(`${API_URL}/nodes`);
                const data = await response.json();
                setNodes(data.nodes || []);
            } catch (error) {
                // Silently handle fetch errors
            }
        };

        load();

        const intervalId = setInterval(load, 15000);

        return () => {
            clearInterval(intervalId);
        };
    }, []);

    return (
        <section className="panel nodes-panel">
            <div className="panel-label">MONITORED NODES</div>
            <div className="section-heading-row">
                <h2>Infrastructure</h2>
                <div className="observed-badge">{nodes.length} NODE{nodes.length !== 1 ? "S" : ""}</div>
            </div>
            {nodes.length === 0 ? (
                <div className="empty-evidence">
                    No nodes reporting yet. Run the collector on a machine.
                </div>
            ) : (
                <div className="nodes-list">
                    {nodes.map((n) => (
                        <div key={n.node_id} className={`node-row node-${n.status}`}>                        
                            <div className="node-name">
                                <span className={`node-dot node-dot-${n.status}`} />
                                <strong>{n.name}</strong>
                            </div>
                            <div className="node-metrics">
                                <span>CPU {Math.round(n.cpu_percent || 0)}%</span>
                                <span>RAM {Math.round(n.ram_percent || 0)}%</span>
                                <span>DISK {Math.round(n.disk_percent || 0)}%</span>
                            </div>
                            <div className="node-status">
                                {String(n.status || "unknown").toUpperCase()} · {n.last_seen_seconds_ago}s ago
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
};

export default NodesPanel;