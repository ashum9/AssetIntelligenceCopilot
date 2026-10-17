"""Chat endpoints for Copilot AI conversations (Standard and SSE streaming)."""

import asyncio
from datetime import datetime, timezone
import json
from typing import Optional, AsyncGenerator, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.agent.orchestrator import CopilotOrchestrator
from backend.schemas.generative_ui import CopilotResponseEnvelope


router = APIRouter(prefix="/api/chat", tags=["Chat"])
_orchestrator = CopilotOrchestrator()


class ChatRequest(BaseModel):
    message: str = Field(..., description="The operator prompt or domain query")
    user_name: str = Field("Michael Turner", description="The acting operator / user identity")
    session_id: Optional[str] = Field(None, description="Optional persistent session identifier")


@router.post("", response_model=CopilotResponseEnvelope)
def chat_standard(req: ChatRequest) -> CopilotResponseEnvelope:
    """Standard non-streaming chat endpoint returning a fully hydrated CopilotResponseEnvelope."""
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        envelope = _orchestrator.ask(
            user_message=clean_msg,
            user_id_or_name=req.user_name,
            session_id=req.session_id,
        )
        return envelope
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Copilot orchestrator error: {str(e)}")


@router.post("/stream")
async def chat_streaming(req: ChatRequest, request: Request):
    """Server-Sent Events (SSE) streaming chat endpoint emitting reasoning progress and envelope."""
    clean_msg = req.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    async def event_generator() -> AsyncGenerator[Dict[str, str], None]:
        # 1. Metadata event
        yield {
            "event": "metadata",
            "data": json.dumps({
                "user_name": req.user_name,
                "session_id": req.session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        }
        await asyncio.sleep(0.01)

        # 2. Progress event: Context resolution
        yield {
            "event": "progress",
            "data": json.dumps({
                "step": "context_resolution",
                "detail": f"Loading private session context for {req.user_name} and checking runtime overrides...",
            }),
        }
        await asyncio.sleep(0.02)

        # 3. Progress event: Telemetry & SQL views
        yield {
            "event": "progress",
            "data": json.dumps({
                "step": "telemetry_retrieval",
                "detail": "Querying DuckDB semantic views and hybrid unstructured index...",
            }),
        }

        # 4. Orchestration execution (run in thread pool to prevent blocking async event loop)
        try:
            loop = asyncio.get_running_loop()
            envelope: CopilotResponseEnvelope = await loop.run_in_executor(
                None,
                _orchestrator.ask,
                clean_msg,
                req.user_name,
                req.session_id,
            )

            # 5. Emit envelope event
            yield {
                "event": "envelope",
                "data": envelope.model_dump_json(),
            }

            # 6. Emit done event
            yield {
                "event": "done",
                "data": json.dumps({"status": "completed"}),
            }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())
