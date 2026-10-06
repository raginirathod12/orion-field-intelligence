"""
ORION Voice Agent API

Backend support for AssemblyAI's Voice Agent API.

The permanent API key stays on the server.
The browser gets a one-time token.

This module also defines the tools that the voice agent
is allowed to call. Tools are executed by the ORION backend,
not by the browser or by AssemblyAI.
"""

from __future__ import annotations

import os
import threading
import uuid
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


load_dotenv()


router = APIRouter(
    prefix="/voice",
    tags=["voice-agent"],
)


ASSEMBLYAI_TOKEN_URL = "https://agents.assemblyai.com/v1/token"


# Storage for background investigations
_completed_investigations: Dict[str, Any] = {}


# -------------------------------------------------------------------
# Agent configuration
# -------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """
=== MOST IMPORTANT RULE ===

The tool result is the ONLY source of truth. When you receive a tool
result, you MUST read it and relay its contents. Never invent numbers,
process names, or outcomes. If the tool says "python3.13 at 90 percent",
you say "python3.13 at 90 percent". If the tool says confidence is
moderate, you say moderate. Do not paraphrase. Do not add. Do not
remove.

After relaying the tool result, IF the tool result mentions a specific
process name, you MUST end your reply by asking: "Would you like me to
suspend it and measure the system?" Do not skip this question.

=== ROLE ===

You are ORION — an evidence-based computer investigation agent.
You investigate why a computer is running slowly by looking at live
telemetry, identifying candidate processes, and explaining your reasoning.

You do not guess. You measure.

=== ABSOLUTE RULES ===

1. NEVER invent numbers, process names, or CPU percentages.
2. NEVER suggest suspending a process until the tool has returned a result.
3. NEVER describe what you found until you have the tool result.
4. If you don't have a tool result yet, say exactly this: "Let me
   investigate that." Then STOP TALKING.

=== SESSION START ===

When the session starts, say exactly:

"Hi, I'm ORION. I investigate why your computer is running slowly
and prove my answers with real measurements. What's going on?"

Then wait. Do not investigate.

=== USER REPORTS A PROBLEM ===

When the user says something like "my laptop is slow":

Step 1. Say: "Got it. Let me investigate that."
        Then STOP TALKING IMMEDIATELY.

Step 2. Call the start_investigation tool. Do NOT say anything else.

Step 3. After the tool returns, say: "Okay, I'm investigating.
        Give me about twenty seconds." Then STOP TALKING and wait.
        The full result will be delivered to you automatically
        in a few seconds.

Step 4. When the full result arrives, relay it exactly as received.
        Speak the candidate name, the CPU number, and the confidence.
        End by asking: "Would you like me to suspend it and measure
        the system?"

=== SMALL TALK ===

For "hello", "thanks", "who are you", "what can you do" — respond
briefly without calling any tools.

=== INTERRUPTION ===

If the user interrupts you mid-sentence, stop immediately and listen.

=== SAFETY ===

Never take action on the user's machine without explicit permission.
""".strip()


AGENT_GREETING = (
    "Hi, I'm ORION. I investigate why your computer is running slowly "
    "and prove my answers with real measurements. What's going on?"
)


AGENT_TOOLS = [
    {
        "type": "function",
        "name": "start_investigation",
        "description": (
            "Start a background investigation of the user's computer. "
            "Use this whenever the user reports a problem: slowness, "
            "lag, high CPU, high memory. Returns immediately with a "
            "started status. The full result will be delivered "
            "separately in about twenty seconds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The user's request in their own words. "
                        "For example: 'my laptop is slow' or "
                        "'why is Chrome using so much CPU'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "get_system_snapshot",
        "description": (
            "Get a quick snapshot of system health right now: CPU "
            "percent, RAM percent, disk status, GPU status. Use "
            "this when the user asks 'how is my system doing' or "
            "wants current numbers without a full investigation."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# -------------------------------------------------------------------
# Token endpoint
# -------------------------------------------------------------------

@router.get("/agent-token")
def voice_agent_token():
    """
    Mint a temporary token for the browser to connect to the
    AssemblyAI Voice Agent WebSocket.

    The permanent API key never leaves the server.
    """

    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ASSEMBLYAI_API_KEY is not configured.",
        )

    try:
        response = requests.get(
            ASSEMBLYAI_TOKEN_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            params={
                "expires_in_seconds": 300,
                "max_session_duration_seconds": 3600,
            },
            timeout=10,
        )
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"Token request failed: {error}",
        )

    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail=(
                f"AssemblyAI token request failed: "
                f"HTTP {response.status_code} {response.text[:200]}"
            ),
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Invalid token response from AssemblyAI.",
        )

    token = data.get("token")
    if not token:
        raise HTTPException(
            status_code=502,
            detail="AssemblyAI returned no token.",
        )

    return {
        "success": True,
        "token": token,
        "system_prompt": AGENT_SYSTEM_PROMPT,
        "greeting": AGENT_GREETING,
        "tools": AGENT_TOOLS,
    }


# -------------------------------------------------------------------
# Tool execution endpoint
# -------------------------------------------------------------------

class ToolCallRequest(BaseModel):
    name: str = Field(..., min_length=1)
    arguments: Dict[str, Any] = Field(default_factory=dict)


@router.post("/agent-tool")
def voice_agent_tool(request: ToolCallRequest):
    """
    Execute a tool that the voice agent called.
    Returns a plain string. The voice agent will speak it.
    """

    name = request.name
    args = request.arguments or {}

    if name == "start_investigation":
        query = args.get("query") or "My laptop is slow. Investigate."

        investigation_id = f"INV-{uuid.uuid4().hex[:10].upper()}"

        # Reserve the slot so polling sees "in_progress"
        _completed_investigations[investigation_id] = None

        def _run_investigation():
            try:
                from agents.orion_agent import orion
                from database.investigation_store import save_investigation

                result = orion.process_structured(query)

                db_id = save_investigation(
                    question=query,
                    result=result,
                )

                if isinstance(result, dict):
                    result["investigation_id"] = db_id

                _completed_investigations[investigation_id] = {
                    "query": query,
                    "result": result,
                    "spoken": _summarize_investigation(result),
                }
                print(
                    f"[BG-INVESTIGATION] {investigation_id} complete"
                )

            except Exception as error:
                print(f"[BG-INVESTIGATION] Failed: {error}")
                _completed_investigations[investigation_id] = {
                    "query": query,
                    "result": {},
                    "spoken": (
                        "I had trouble running the investigation. "
                        "Please try again."
                    ),
                }

        threading.Thread(
            target=_run_investigation,
            daemon=True,
        ).start()

        return {
            "success": True,
            "spoken": "Okay, I'm investigating now.",
            "investigation_id": investigation_id,
            "status": "started",
        }

    if name == "get_system_snapshot":
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/")
            disk_free_gb = disk.free / (1024 ** 3)

            spoken = (
                f"Right now, CPU is at {cpu:.0f} percent. "
                f"Memory is at {ram:.0f} percent. "
                f"You have {disk_free_gb:.0f} gigabytes of free disk space. "
            )

            if cpu > 80:
                spoken += "CPU is unusually high."
            elif ram > 85:
                spoken += "Memory pressure looks high."
            else:
                spoken += "Everything looks within normal range."

            return {
                "success": True,
                "spoken": spoken,
                "cpu_percent": cpu,
                "ram_percent": ram,
                "disk_free_gb": disk_free_gb,
            }

        except Exception as error:
            print(f"[VOICE-AGENT TOOL] snapshot failed: {error}")
            return {
                "success": False,
                "spoken": "I couldn't read the system snapshot.",
            }

    return {
        "success": False,
        "spoken": f"I don't have a tool called {name}.",
    }


# -------------------------------------------------------------------
# Background investigation status polling
# -------------------------------------------------------------------

@router.get("/investigation-status/{investigation_id}")
def investigation_status(investigation_id: str):
    """
    Check if a background investigation has finished.
    """
    if investigation_id not in _completed_investigations:
        return {"status": "not_found"}

    entry = _completed_investigations.get(investigation_id)

    if entry is None:
        return {"status": "in_progress"}

    return {
        "status": "complete",
        "query": entry["query"],
        "result": entry["result"],
        "spoken": entry["spoken"],
    }


# -------------------------------------------------------------------
# Helper
# -------------------------------------------------------------------

def _summarize_investigation(result: dict) -> str:
    """
    Build a short spoken summary from a structured investigation.
    """

    if not isinstance(result, dict):
        return "I couldn't process that investigation."

    diagnosis = result.get("diagnosis") or {}
    observation = diagnosis.get("observation") or ""
    confidence = (diagnosis.get("confidence") or "").upper()

    investigation = result.get("investigation") or {}
    strongest = investigation.get("strongest_evidence") or {}

    sentences = []
    sentences.append("Alright, I found something.")

    if observation:
        first = observation.split(". ")[0].strip()
        if first:
            sentences.append(first + ".")

    name = strongest.get("process")
    if name:
        clean = str(name).replace(".exe", "")
        cpu = strongest.get("cpu_percent")
        if cpu is not None:
            sentences.append(
                f"The strongest candidate is {clean}, "
                f"using about {round(cpu)} percent CPU."
            )
        else:
            sentences.append(f"The strongest candidate is {clean}.")

    if confidence == "HIGH":
        sentences.append("My confidence is high. The evidence is strong.")
    elif confidence == "MODERATE":
        sentences.append(
            "My confidence is moderate. I'd like to verify "
            "with a measurement."
        )
    elif confidence == "LOW":
        sentences.append(
            "My confidence is low. I have some evidence but "
            "not enough to be sure."
        )

    if name:
        sentences.append(
            "Would you like me to temporarily suspend it and "
            "measure whether your system actually improves?"
        )
    else:
        sentences.append("Would you like me to investigate something else?")

    return " ".join(sentences).strip()