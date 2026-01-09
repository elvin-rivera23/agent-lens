# Configuration Reference

AgentLens can be configured via environment variables and Docker Compose profiles.

---

## Docker Profiles

Start with the appropriate profile for your hardware:

```bash
# GPU mode (requires NVIDIA GPU + Docker GPU runtime)
docker compose --profile gpu up

# CPU mode (uses Ollama for inference)
docker compose --profile cpu up
```

| Profile | Inference Engine | Model | Requirements |
|---------|-----------------|-------|--------------|
| `gpu` | vLLM | Llama-3/Phi-2 | NVIDIA GPU, 8GB+ VRAM |
| `cpu` | Ollama | Mistral 7B | 16GB+ RAM recommended |

---

## Environment Variables

Copy `.env.example` to `.env` and customize:

### Inference Engine

| Variable | Default | Description |
|----------|---------|-------------|
| `INFERENCE_MODEL` | `meta-llama/Llama-3.2-3B-Instruct` | HuggingFace model ID |
| `INFERENCE_QUANTIZATION` | `none` | Quantization: `none`, `awq`, `gptq` |
| `INFERENCE_MAX_MODEL_LEN` | `8192` | Context window size |
| `INFERENCE_GPU_MEMORY_UTILIZATION` | `0.85` | GPU memory fraction (0.0-1.0) |
| `FALLBACK_MODEL` | `microsoft/Phi-3-mini-4k-instruct` | Fallback for low memory |

### Orchestrator

| Variable | Default | Description |
|----------|---------|-------------|
| `INFERENCE_URL` | `http://inference:8000` | Inference server URL |
| `WORKSPACE_DIR` | `/workspace` | Generated code directory |
| `AGENT_TIMEOUT` | `60` | Agent timeout in seconds |
| `MAX_CONCURRENT_AGENTS` | `2` | Max parallel agents |

### Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_PORT` | `3000` | Dashboard web port |
| `VITE_ORCHESTRATOR_URL` | `http://localhost:8001` | Backend URL |
| `VITE_WS_URL` | `ws://localhost:8001` | WebSocket URL |

### Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `PROMETHEUS_PORT` | `9090` | Prometheus UI port |
| `GRAFANA_PORT` | `3001` | Grafana UI port |
| `METRICS_SCRAPE_INTERVAL` | `5` | Scrape interval (seconds) |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `agentlens` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password |
| `POSTGRES_DB` | `agentlens` | Database name |

---

## Model Compatibility

| Model | Quantization | VRAM | Tokens/sec | Latency p50 | Notes |
|-------|--------------|------|------------|-------------|-------|
| Llama-3-8B | Q8 | ~10GB | ~50 | 180ms | Best quality |
| Llama-3-8B | Q4 | ~6GB | ~65 | 140ms | Good balance |
| Phi-3-mini | Q4 | ~4GB | ~80 | 100ms | Fastest |
| Mistral 7B | - | ~8GB | ~45 | 200ms | CPU mode (Ollama) |

*Benchmarks on RTX 4080 Super (GPU) / Ryzen 9 5900X (CPU)*

---

## Local Development

For development without Docker:

```bash
# 1. Start Ollama
ollama serve
ollama pull mistral

# 2. Start Orchestrator
cd services/orchestrator
pip install -r requirements.txt
$env:INFERENCE_URL='http://localhost:11434'
$env:WORKSPACE_DIR='./workspace'
cd src && python -m uvicorn main:app --port 8001 --reload

# 3. Start Dashboard
cd services/dashboard
npm install && npm run dev
```

Access at:
- Dashboard: http://localhost:5173
- Orchestrator API: http://localhost:8001
- Prometheus: http://localhost:9090 (if running)
