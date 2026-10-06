"""
FastAPI router for multi-node telemetry.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from nodes.registry import get_node, list_nodes, register_node

router = APIRouter(prefix="/nodes", tags=["nodes"])

class NodeReport(BaseModel):
    node_id: str
    name: str
    cpu_percent: float
    ram_percent: float
    disk_percent: float
    uptime_hours: float


@router.post("/report")
async def report_node(report: NodeReport) -> dict:
    register_node(report.node_id, report.model_dump())
    return {"success": True}


@router.get("")
async def list_nodes_endpoint() -> dict:
    return {"success": True, "nodes": list_nodes()}


@router.get("/{node_id}")
async def get_node_endpoint(node_id: str) -> dict:
    data = get_node(node_id)
    if data is None:
        return {"success": False, "error": "Node not found."}
    return {"success": True, "node": data}
