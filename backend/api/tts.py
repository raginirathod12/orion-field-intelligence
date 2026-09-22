"""
ORION Text-to-Speech API
"""

import tempfile

import edge_tts
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse


router = APIRouter(
    prefix="/tts",
    tags=["tts"],
)


VOICE = "en-US-AriaNeural"


@router.get("/speak")
async def speak(
    text: str = Query(..., min_length=1, max_length=1000),
):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text is empty.")

    clean = (
        text.replace("*", "")
        .replace("#", "")
        .replace("_", "")
        .replace("`", "")
        .replace(">", "")
        .replace("|", "")
        .strip()
    )

    if not clean:
        raise HTTPException(
            status_code=400,
            detail="Text is empty after cleaning.",
        )

    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()

        communicate = edge_tts.Communicate(clean, VOICE)
        await communicate.save(tmp.name)

        return FileResponse(
            tmp.name,
            media_type="audio/mpeg",
            filename="orion_voice.mp3",
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"TTS failed: {error}",
        )