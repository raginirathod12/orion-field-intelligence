"""
ORION Voice API

Health check + short-lived streaming token endpoint.

The permanent AssemblyAI API key stays on the server.
The browser receives only a temporary token.
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException


load_dotenv()


router = APIRouter(
    prefix="/voice",
    tags=["voice"],
)


# ----------------------------------------------------------------------
# Health check
# ----------------------------------------------------------------------

@router.get("/health")
def voice_health():
    api_key_present = bool(os.getenv("ASSEMBLYAI_API_KEY"))

    microphone_available = False
    microphone_error = None

    try:
        import pyaudio

        p = pyaudio.PyAudio()
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    microphone_available = True
                    break
        finally:
            p.terminate()
    except Exception as error:
        microphone_error = str(error)

    return {
        "success": api_key_present and microphone_available,
        "api_key_present": api_key_present,
        "microphone_available": microphone_available,
        "microphone_error": microphone_error,
        "provider": "AssemblyAI",
        "mode": "realtime-v3",
    }


# ----------------------------------------------------------------------
# Short-lived streaming token (for browser clients)
# ----------------------------------------------------------------------

@router.get("/token")
def voice_token():
    """
    Generate a short-lived AssemblyAI streaming token.

    Tries the v3 endpoint first, falls back to v1 if needed.
    The permanent API key never leaves the backend.
    """

    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="ASSEMBLYAI_API_KEY is not configured.",
        )

    candidate_urls = [
        "https://streaming.assemblyai.com/v3/token",
        "https://api.assemblyai.com/v1/realtime/token",
    ]

    last_error = None

    for url in candidate_urls:
        try:
            response = requests.get(
                url,
                headers={"Authorization": api_key},
                params={"expires_in_seconds": 300},
                timeout=10,
            )
        except requests.RequestException as error:
            last_error = f"{url}: {error}"
            continue

        if not response.ok:
            last_error = (
                f"{url}: HTTP {response.status_code} {response.text[:200]}"
            )
            continue

        try:
            data = response.json()
        except ValueError:
            last_error = f"{url}: invalid JSON"
            continue

        token = data.get("token") or data.get("access_token")
        if not token:
            last_error = f"{url}: no 'token' field. Body: {str(data)[:200]}"
            continue

        return {
            "success": True,
            "token": token,
            "expires_in_seconds": 300,
            "source": url,
        }

    raise HTTPException(
        status_code=502,
        detail=f"AssemblyAI token request failed. Tried: {last_error}",
    )