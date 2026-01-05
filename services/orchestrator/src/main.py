"""
AgentLens Orchestrator Service

FastAPI application for multi-agent code generation and execution.
"""

import logging
from contextlib import asynccontextmanager

from events import broadcaster
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from graph import cleanup, run_orchestration
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from state import OrchestratorState
from telemetry import ORCHESTRATION_REQUESTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class OrchestrationRequest(BaseModel):
    """Request body for /orchestrate endpoint."""

    task: str = Field(..., description="The coding task to execute", min_length=1)
    max_retries: int = Field(default=3, description="Maximum retry attempts", ge=0, le=10)


class OrchestrationResponse(BaseModel):
    """Response from /orchestrate endpoint."""

    success: bool
    task: str
    code: str
    file_path: str
    execution_output: str
    retries: int
    history: list[dict]


# =============================================================================
# Application Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting AgentLens Orchestrator...")
    yield
    logger.info("Shutting down AgentLens Orchestrator...")
    await cleanup()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="AgentLens Orchestrator",
    description="Multi-agent code generation and execution with Glass-Box observability",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# Endpoints
# =============================================================================


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "orchestrator",
        "version": "0.1.0",
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(request: OrchestrationRequest):
    """
    Execute a coding task through the agent pipeline.

    The pipeline:
    1. Coder Agent generates Python code and writes it to /workspace
    2. Executor Agent runs the code and captures output
    3. On failure, retry up to max_retries times

    Returns the final state including code, output, and execution history.
    """
    logger.info(f"Received orchestration request: {request.task[:100]}...")
    ORCHESTRATION_REQUESTS.inc()

    try:
        # Create initial state with custom max_retries if provided
        final_state: OrchestratorState = await run_orchestration(request.task)

        return OrchestrationResponse(
            success=final_state.execution_success,
            task=final_state.task,
            code=final_state.code,
            file_path=final_state.file_path,
            execution_output=final_state.execution_output,
            retries=final_state.error_count,
            history=final_state.history,
        )

    except Exception as e:
        logger.exception(f"Orchestration failed: {e}")
        return OrchestrationResponse(
            success=False,
            task=request.task,
            code="",
            file_path="",
            execution_output=f"Orchestration error: {e}",
            retries=0,
            history=[],
        )


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time agent events.

    Events are broadcast as JSON:
    {
        "type": "agent_start" | "agent_end" | "token" | "code_written" | "execution" | "error",
        "agent": "coder" | "executor" | "orchestrator",
        "timestamp": 1234567890.123,
        "data": { ... event-specific data ... }
    }
    """
    await broadcaster.connect(websocket)

    try:
        while True:
            # Keep connection alive, client doesn't send data
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
