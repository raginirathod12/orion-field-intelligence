from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.orion_agent import orion
from database.investigation_store import (
    get_investigation,
    list_investigations,
    save_investigation,
)
from api.remediation import router as remediation_router
from api.voice import router as voice_router


app = FastAPI(
    title="ORION Field Intelligence",
    description="AI-powered field intelligence assistant",
    version="0.5.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------
# Routers
# ----------------------------------------------------------------

app.include_router(remediation_router)
app.include_router(voice_router)


# ----------------------------------------------------------------
# Core endpoints
# ----------------------------------------------------------------

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "ORION Field Intelligence is operational.",
        "version": "0.5.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/ask")
def ask_orion(message: str):

    if not message or not message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    try:
        result = orion.process_structured(message)

        investigation_id = save_investigation(
            question=message,
            result=result,
        )

        if isinstance(result, dict):
            result["investigation_id"] = investigation_id

        return result

    except Exception as error:

        print(f"ORION API ERROR: {error}")

        raise HTTPException(
            status_code=500,
            detail="ORION failed to process the request.",
        )


@app.get("/investigations")
def investigations(limit: int = 20):

    try:
        return {
            "success": True,
            "investigations": list_investigations(limit),
        }

    except Exception as error:

        print(f"ORION HISTORY ERROR: {error}")

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve investigation history.",
        )


@app.get("/investigations/{investigation_id}")
def investigation(investigation_id: str):

    try:
        result = get_investigation(investigation_id)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Investigation not found.",
            )

        return {
            "success": True,
            "investigation": result,
        }

    except HTTPException:
        raise

    except Exception as error:

        print(f"ORION INVESTIGATION ERROR: {error}")

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve investigation.",
        )