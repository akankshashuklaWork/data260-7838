"""Routes for chat, MongoDB memory inspection, and aggregate statistics."""

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from ..memory import aggregate_snapshot, memory_snapshot, run_chat
from ..schemas import ChatRequest


router = APIRouter(prefix="/api", tags=["memory"])


@router.post("/chat")
def chat(payload: ChatRequest) -> dict:
    try:
        return run_chat(payload.user_id, payload.session_id, payload.message)
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error during chat") from error
    except ConnectionError as error:
        raise HTTPException(status_code=503, detail="local model is unavailable") from error
    except Exception as error:
        if error.__class__.__name__ in {"ConnectError", "OllamaEndpointNotFoundError"}:
            raise HTTPException(status_code=503, detail="local Ollama model is unavailable") from error
        raise HTTPException(status_code=500, detail="chat request failed") from error


@router.get("/memory/{user_id}")
def get_memory(user_id: str) -> dict:
    try:
        return memory_snapshot(user_id)
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while reading memory") from error


@router.get("/aggregate/{user_id}")
def get_aggregate(user_id: str) -> dict:
    try:
        return aggregate_snapshot(user_id)
    except PyMongoError as error:
        raise HTTPException(status_code=500, detail="database error while aggregating memory") from error
