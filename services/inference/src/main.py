"""
AgentLens Inference Service - CPU Mode
OpenAI-compatible API using llama-cpp-python
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel

from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics
REQUEST_COUNT = Counter("inference_requests_total", "Total inference requests")
REQUEST_LATENCY = Histogram(
    "inference_latency_seconds",
    "Inference latency",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
TOKENS_GENERATED = Counter("inference_tokens_generated_total", "Total tokens generated")
MODEL_LOADED = Gauge("inference_model_loaded", "Whether model is loaded (1=yes, 0=no)")
ACTIVE_REQUESTS = Gauge("inference_active_requests", "Number of active inference requests")

# Lighthouse Metrics - Portfolio Differentiators
TOKENS_PER_SECOND = Histogram(
    "inference_tokens_per_second",
    "Token generation throughput (TPS)",
    buckets=[1, 5, 10, 20, 50, 100, 200, 500],
)
TIME_TO_FIRST_TOKEN = Histogram(
    "inference_time_to_first_token_seconds",
    "Time to first token (TTFT) - agent responsiveness",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)
VRAM_MODEL_BYTES = Gauge(
    "inference_vram_model_bytes",
    "VRAM used by model weights",
)
VRAM_CONTEXT_BYTES = Gauge(
    "inference_vram_context_bytes",
    "VRAM used by KV cache / context",
)

# Model instance
model = None


class CompletionRequest(BaseModel):
    model: str = "default"
    prompt: str
    max_tokens: int = 256
    temperature: float = 0.7
    stop: list[str] | None = None
    stream: bool = False


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: list[ChatMessage]
    max_tokens: int = 256
    temperature: float = 0.7
    stream: bool = False


class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    choices: list[dict]
    usage: dict


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    choices: list[dict]
    usage: dict


def load_model():
    """Load llama-cpp model."""
    global model

    try:
        from llama_cpp import Llama

        logger.info(f"Loading model from {settings.model_path}")
        model = Llama(
            model_path=settings.model_path,
            n_ctx=settings.context_length,
            n_threads=4,
            verbose=False,
        )
        MODEL_LOADED.set(1)
        logger.info("Model loaded successfully")
    except FileNotFoundError:
        logger.warning(f"Model file not found at {settings.model_path}, running in placeholder mode")
        model = None
        MODEL_LOADED.set(0)
    except ImportError:
        logger.warning("llama-cpp-python not installed, running in placeholder mode")
        model = None
        MODEL_LOADED.set(0)
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        model = None
        MODEL_LOADED.set(0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    load_model()
    yield
    logger.info("Shutting down inference service")


app = FastAPI(
    title="AgentLens Inference (CPU)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": settings.mode,
        "model_loaded": model is not None,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def generate_completion(prompt: str, max_tokens: int, temperature: float) -> tuple[str, int, float]:
    """Generate completion using the model or placeholder.

    Returns:
        tuple: (response_text, token_count, generation_time_seconds)
    """
    start_time = time.time()

    if model is None:
        # Placeholder response when no model
        await asyncio.sleep(0.1)  # Simulate some latency
        response_text = f"[Placeholder] Echo: {prompt[:100]}..."
        token_count = len(response_text.split())
        generation_time = time.time() - start_time
        return response_text, token_count, generation_time

    # Run inference in thread pool to not block event loop
    loop = asyncio.get_event_loop()

    def _generate():
        output = model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            echo=False,
        )
        return output["choices"][0]["text"], output["usage"]["completion_tokens"]

    try:
        response_text, tokens = await asyncio.wait_for(
            loop.run_in_executor(None, _generate),
            timeout=settings.inference_timeout,
        )
        generation_time = time.time() - start_time
        return response_text, tokens, generation_time
    except asyncio.TimeoutError as e:
        raise HTTPException(status_code=504, detail="Inference timeout exceeded") from e



async def stream_completion(prompt: str, max_tokens: int, temperature: float) -> AsyncGenerator[str, None]:
    """Stream completion tokens with Lighthouse metrics (TTFT, TPS)."""
    start_time = time.time()
    first_token_time = None
    token_count = 0

    if model is None:
        # Placeholder streaming with simulated metrics
        words = f"[Placeholder] Echo: {prompt[:50]}...".split()
        for i, word in enumerate(words):
            if i == 0:
                first_token_time = time.time()
                TIME_TO_FIRST_TOKEN.observe(first_token_time - start_time)
            token_count += 1
            yield f"data: {word} \n\n"
            await asyncio.sleep(0.05)

        # Record TPS
        total_time = time.time() - start_time
        if total_time > 0:
            TOKENS_PER_SECOND.observe(token_count / total_time)
        TOKENS_GENERATED.inc(token_count)

        yield "data: [DONE]\n\n"
        return

    # Real streaming with llama-cpp
    loop = asyncio.get_event_loop()

    def _stream():
        return model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )

    stream = await loop.run_in_executor(None, _stream)

    for chunk in stream:
        if first_token_time is None:
            first_token_time = time.time()
            TIME_TO_FIRST_TOKEN.observe(first_token_time - start_time)

        token = chunk["choices"][0]["text"]
        token_count += 1
        yield f"data: {token}\n\n"

    # Record TPS after streaming completes
    total_time = time.time() - start_time
    if total_time > 0 and token_count > 0:
        TOKENS_PER_SECOND.observe(token_count / total_time)
    TOKENS_GENERATED.inc(token_count)

    yield "data: [DONE]\n\n"


@app.post("/v1/completions")
async def completions(request: CompletionRequest):
    """OpenAI-compatible completions endpoint."""
    REQUEST_COUNT.inc()
    ACTIVE_REQUESTS.inc()

    try:
        start_time = time.time()

        if request.stream:
            return StreamingResponse(
                stream_completion(request.prompt, request.max_tokens, request.temperature),
                media_type="text/event-stream",
            )

        response_text, completion_tokens, gen_time = await generate_completion(
            request.prompt, request.max_tokens, request.temperature
        )

        latency = time.time() - start_time
        REQUEST_LATENCY.observe(latency)
        TOKENS_GENERATED.inc(completion_tokens)
        if gen_time > 0 and completion_tokens > 0:
            TOKENS_PER_SECOND.observe(completion_tokens / gen_time)

        return CompletionResponse(
            id=f"cmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            choices=[{"text": response_text, "index": 0, "finish_reason": "stop"}],
            usage={
                "prompt_tokens": len(request.prompt.split()),
                "completion_tokens": completion_tokens,
                "total_tokens": len(request.prompt.split()) + completion_tokens,
            },
        )
    finally:
        ACTIVE_REQUESTS.dec()


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint."""
    REQUEST_COUNT.inc()
    ACTIVE_REQUESTS.inc()

    try:
        start_time = time.time()

        # Convert messages to prompt
        prompt = "\n".join([f"{m.role}: {m.content}" for m in request.messages])
        prompt += "\nassistant:"

        if request.stream:
            return StreamingResponse(
                stream_completion(prompt, request.max_tokens, request.temperature),
                media_type="text/event-stream",
            )

        response_text, completion_tokens, gen_time = await generate_completion(
            prompt, request.max_tokens, request.temperature
        )

        latency = time.time() - start_time
        REQUEST_LATENCY.observe(latency)
        TOKENS_GENERATED.inc(completion_tokens)
        if gen_time > 0 and completion_tokens > 0:
            TOKENS_PER_SECOND.observe(completion_tokens / gen_time)

        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            usage={
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": completion_tokens,
                "total_tokens": len(prompt.split()) + completion_tokens,
            },
        )
    finally:
        ACTIVE_REQUESTS.dec()


@app.post("/generate")
async def generate(request: CompletionRequest):
    """Simple generate endpoint with streaming support."""
    if request.stream:
        return StreamingResponse(
            stream_completion(request.prompt, request.max_tokens, request.temperature),
            media_type="text/event-stream",
        )

    response_text, _, _ = await generate_completion(
        request.prompt, request.max_tokens, request.temperature
    )
    return {"text": response_text}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
