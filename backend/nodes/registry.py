from __future__ import annotations

"""
ORION multi-node monitoring registry.
"""

import time
import typing

_nodes: dict[str, dict] = {}

STALE_AFTER_SECONDS = 60


def register_node(node_id: str, payload: dict) -> None:
    _nodes[node_id] = {**payload, "last_seen": time.time()}


def list_nodes() -> list[dict]:
    nodes = []
    for node_id, data in _nodes.items():
        alive = (time.time() - data["last_seen"]) < STALE_AFTER_SECONDS
        status = "online" if alive else "offline"
        last_seen_seconds_ago = int(time.time() - data["last_seen"])
        node_info = {
            "node_id": node_id,
            "name": data.get("name", "Unknown"),
            "cpu_percent": data.get("cpu_percent", 0),
            "ram_percent": data.get("ram_percent", 0),
            "disk_percent": data.get("disk_percent", 0),
            "uptime_hours": int(data.get("uptime_seconds", 0) / 3600),
            "status": status,
            "last_seen_seconds_ago": last_seen_seconds_ago,
        }
        nodes.append(node_info)
    return sorted(nodes, key=lambda x: x["node_id"])


def get_node(node_id: str) -> dict | None:
    return _nodes.get(node_id)
