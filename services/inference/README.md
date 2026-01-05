# Inference Service

GPU-accelerated LLM inference using vLLM.

## Development

```bash
# Build
docker build -t agentlens-inference .

# Run
docker run --gpus all -p 8000:8000 agentlens-inference
```

## Endpoints

- `POST /v1/completions` - OpenAI-compatible completions
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
