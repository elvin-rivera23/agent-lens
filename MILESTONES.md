# AgentLens Milestones

> 🔒 **Private roadmap** - This file is gitignored for internal tracking only.

---

## M0: Project Foundation 🧱
**Goal:** CI/CD and testing infrastructure that gates ALL subsequent work

> ⚠️ **This milestone runs continuously** - Every PR in M1-M5 must pass these gates

### Development Environment
- [x] Python virtual environment setup script
- [x] Pre-commit hooks (black, ruff, mypy)
- [x] VS Code / IDE settings in `.vscode/`
- [x] Makefile or just commands for common tasks

### CI/CD Pipeline (Enforced on Every PR)
- [x] GitHub Actions workflow triggered on PR
- [x] Lint gate (ruff)
- [x] Type check gate (mypy)
- [x] Unit test gate (pytest)
- [x] Docker build verification
- [x] Container image caching for speed

### Testing Infrastructure
- [x] pytest setup with fixtures
- [x] Mock fixtures for LLM responses

> ℹ️ *Test coverage & integration harness deferred to M4*

### Branch Strategy
- [x] `main` protected - requires PR + passing checks
- [x] Feature branches: `feature/<milestone>-<description>`
- [x] PR template with checklist

**✅ Deliverable:** Every commit is gated by automated quality checks

---

## M1: Core Infrastructure 🏗️
**Goal:** End-to-end pipeline working with CPU-only profile

### Inference Service (`services/inference`)
- [x] FastAPI server implementation
- [x] llama-cpp-python integration for CPU inference
- [x] `/generate` endpoint with streaming SSE support
- [x] `/health` endpoint for container orchestration
- [x] Model loading with configurable path (env vars)
- [x] Request timeout handling (60s max)
- [x] Unit tests for endpoints

> ℹ️ *Context compression deferred to M4*

### Metrics Collector (`services/metrics`)
- [x] Basic system stats (CPU, memory, disk)
- [x] Inference request counter
- [x] Latency histogram (p50, p95, p99)
- [x] Prometheus `/metrics` endpoint
- [x] Unit tests for metrics collection

### Integration
- [x] Prometheus scraping inference + metrics services
- [x] `docker compose --profile cpu up` working
- [x] Verify metrics appear in Prometheus UI

> ℹ️ *Automated integration tests deferred to M4*

**✅ Deliverable:** Working pipeline: Inference → Metrics → Prometheus

---

## M2: GPU Observability 🎮
**Goal:** Real GPU telemetry + Lighthouse Metrics

### NVML Integration
- [x] GPU utilization % (core + memory)
- [x] GPU temperature monitoring
- [x] VRAM usage tracking (total, used, free)
- [x] Multi-GPU enumeration support
- [x] Graceful handling when no GPU available

### Lighthouse Metrics (Key Differentiators)
- [x] **TPS (Tokens Per Second)** - Live throughput per agent
- [x] **TTFT (Time to First Token)** - Agent responsiveness
- [x] **VRAM Occupancy** - Cache vs active weights breakdown

### GPU Docker Profile
- [x] NVIDIA runtime configuration
- [x] GPU resource limits in compose
- [x] GPU simulation mode for local development

**✅ Deliverable:** Real GPU metrics + Lighthouse Metrics in Prometheus

---

## M3: Multi-Agent Vertical Slice 🤖
**Goal:** Working Coder + Executor agents with real tools and Glass-Box visibility

> 🎯 **Strategy:** Build 2 agents that *actually work* end-to-end, then expand.

### Orchestrator Service (`services/orchestrator/`)
- [x] Dockerfile with sandboxed `/workspace` directory
- [x] FastAPI app with `/orchestrate`, `/health`, `/metrics` endpoints
- [x] LangGraph StateGraph integration
- [x] WebSocket `/ws/events` for real-time streaming

### Agent Implementation
- [x] **Coder Agent** - Code generation + *real file writing*
- [x] **Executor Agent** - *Real command execution* (sandboxed)
- [x] Retry loop: Executor fail → Coder retry (max 3)

### LangGraph State Machine
- [x] `OrchestratorState` Pydantic model
- [x] Coder → Executor graph with conditional retry edge
- [x] Error handling and timeout (60s)

### Glass-Box Telemetry (Key Differentiator)
- [x] Per-agent Prometheus metrics (invocations, duration, tokens)
- [x] `orchestrator_current_agent` gauge for correlation
- [x] WebSocket event broadcasting (agent_start, token, agent_end)

### Testing
- [x] Unit tests for code parsing and command whitelist

> ℹ️ *Integration tests & Docker verification deferred to M4*

**✅ Deliverable:** Demo: "Write fibonacci" → Code written → Executed → Glass-Box metrics

---

## M3.5: Full Multi-Agent System 🤖🤖🤖🤖
**Goal:** Expand to 4-agent team with basic orchestration

### Additional Agents
- [x] **Architect Agent** - System design, task decomposition
- [x] **Reviewer Agent** - Code review, quality checks

### Orchestration
- [x] Full 4-agent handoff chain (Architect → Coder → Reviewer → Executor)

**✅ Deliverable:** 4-agent team with handoff chain working

---

## M4: Production Hardening 🔧
**Goal:** Real inference backends, error recovery, and production-ready orchestration

> 🎯 **Priority:** Actual functionality before UI polish

### GPU Inference Backend
- [x] vLLM server as alternative runtime
- [x] Runtime selection via `INFERENCE_RUNTIME` env var
- [x] KV cache utilization tracking
- [x] Tiered model selection based on VRAM
- [x] Automatic fallback on OOM or CUDA unavailable

### CPU Inference Backend (Ollama)
- [x] Ollama container for CPU inference (Mistral 7B)
- [x] Automatic model pull on first run (`ollama-pull` service)
- [x] Orchestrator connected to Ollama container
- [x] Mock mode removed - real LLM inference only

### Advanced Orchestration
- [x] Windows subprocess compatibility fix (asyncio → subprocess.run)
- [x] Single-file code generation prompt hardening
- [x] Conversation memory / context passing
- [x] Error classification (syntax, runtime, logic)

### Error Recovery
- [x] JSON parse failure → "Format Fix" re-prompt
- [x] Single agent crash → bypass or fallback
- [x] Conditional retry edges (reviewer→coder, executor→coder)
- [x] Inference disconnect → queue + reconnect

### Tool Integration
- [x] Code search / grep tools for Architect
- [x] File read tools for Architect

### Testing Infrastructure (from M0/M1)
- [x] Test coverage reporting (target: 80%+)
- [x] Integration test harness (docker-compose based)
- [x] Integration tests for Coder → Executor flow
- [x] Context compression fallback on timeout

**✅ Deliverable:** Production-ready inference and orchestration with robust error handling

---

## M5: Cyberpunk Dashboard 🌆
**Goal:** Portfolio-ready real-time HUD

### Dashboard Framework (`services/dashboard`)
- [x] React + TypeScript setup (Vite)
- [x] WebSocket connection hook to backend
- [x] Dark theme base (Deep Black #0a0a0f)

### Real-Time Data Flow
- [x] WebSocket stream: tokens + telemetry merged
- [x] WebSocket URL fix (port 8002 → 8001)
- [x] Real-time code output display from events
- [ ] Live token generation display
- [x] Agent state change animations

### Agent Status Cards
- [x] Status indicator (idle/working/blocked)
- [ ] Live token stream panel
- [ ] Per-agent metrics: Tokens | Latency | VRAM
- [ ] Reasoning drawer (expandable JSON/prompt)

### GPU Telemetry Panels
- [ ] GPU utilization gauge (arc/circular)
- [ ] VRAM distribution bar (cache vs weights)
- [ ] Temperature indicator
- [ ] Token throughput sparkline

### Enhanced Glass-Box (from M3.5)
- [ ] Map GPU spikes to active agent in timeline
- [ ] Per-agent resource attribution
- [ ] Agent activity timeline with GPU overlay

### Timeline & History
- [x] Agent handoff timeline rail (AgentTimeline component)
- [ ] Task progress visualization

### Visual Polish (Cyberpunk/Mecha HUD)
- [x] Colors: Cyan #00f0ff, Orange #ff6b00, Magenta #ff00aa
- [x] Fonts: JetBrains Mono (code), Orbitron (headers)
- [x] HUD frames with corner brackets
- [x] Subtle scan lines, glitch effects, glow

**✅ Deliverable:** Stunning demo UI for portfolio

---

## M6: Demo & Documentation 📽️
**Goal:** Make it presentable and shareable

### Demo Assets
- [ ] Screen recording of full workflow
- [ ] GIF clips for README/LinkedIn
- [ ] Architecture diagram (polished Mermaid)
- [ ] Performance benchmark results

### Documentation
- [ ] README with quick start guide
- [ ] API documentation (OpenAPI)
- [ ] Configuration reference
- [ ] Model compatibility matrix

### Portfolio Integration
- [ ] LinkedIn post draft
- [ ] GitHub profile pin
- [ ] Portfolio site integration

**✅ Deliverable:** Complete, portfolio-ready project

---

## Progress Tracker

| Milestone | Status | Started | Completed |
|-----------|--------|---------|-----------|
| M0: Project Foundation | ✅ Complete | 2026-01-04 | 2026-01-04 |
| M1: Core Infrastructure | ✅ Complete | 2026-01-04 | 2026-01-05 |
| M2: GPU Observability | ✅ Complete | 2026-01-05 | 2026-01-05 |
| M3: Multi-Agent Vertical Slice | ✅ Complete | 2026-01-05 | 2026-01-05 |
| M3.5: Full Multi-Agent System | ✅ Complete | 2026-01-05 | 2026-01-05 |
| M4: Production Hardening | ⚡ Partial | 2026-01-06 | - |
| M5: Cyberpunk Dashboard | ⚡ Partial | 2026-01-05 | - |
| M6: Demo & Documentation | 🔲 Not Started | - | - |

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Inference (CPU) | llama-cpp-python | Portable, Mac M1 compatible |
| Inference (GPU) | vLLM | High throughput, OpenAI-compatible |
| Orchestration | LangGraph | State machine for multi-agent |
| Metrics | Prometheus | Industry standard |
| Dashboard | React + WebSocket | Real-time, customizable HUD |

---

## Model Recommendations

| Hardware | Primary Model | Fallback | VRAM |
|----------|---------------|----------|------|
| GPU High | Llama-3-8B Q8 | Llama-3-8B Q4 | ~10.5GB |
| GPU Mid | Llama-3-8B Q4 | Phi-3-mini-4k | ~6.5GB |
| CPU/Mac | Phi-3-mini-4k | Phi-3-mini Q4 | ~4.2GB |

---

## 🧹 Post-Project Cleanup

> **Run after project is complete** - Removes development tools installed globally

### Uninstall Checklist
- [ ] **Docker Desktop** - Settings → Uninstall or Add/Remove Programs
- [ ] **WSL2** - `wsl --unregister docker-desktop` then Add/Remove Programs → Windows Subsystem for Linux
- [ ] **Ollama** - Add/Remove Programs → Ollama
- [ ] **Ollama Models** - Delete `%USERPROFILE%\.ollama\models\` folder
- [ ] **Global pip packages** - `pip uninstall pygame` (if installed globally)
- [ ] **HuggingFace cache** - Delete `%USERPROFILE%\.cache\huggingface\` (model downloads)

### Windows Cleanup Commands
```powershell
# Remove Ollama models (~5GB+)
Remove-Item -Recurse -Force "$env:USERPROFILE\.ollama"

# Remove HuggingFace cache
Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\huggingface"

# Uninstall pygame if installed globally
pip uninstall pygame -y
```

