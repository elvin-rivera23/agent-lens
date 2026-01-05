"""
AgentLens Metrics Collector Service
Collects system metrics and exposes them for Prometheus
"""

import logging
import time

import psutil
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AgentLens Metrics Collector", version="0.1.0")

# System metrics
CPU_USAGE = Gauge("system_cpu_usage_percent", "CPU usage percentage")
MEMORY_USAGE = Gauge("system_memory_usage_percent", "Memory usage percentage")
MEMORY_USED_BYTES = Gauge("system_memory_used_bytes", "Memory used in bytes")
MEMORY_TOTAL_BYTES = Gauge("system_memory_total_bytes", "Total memory in bytes")
DISK_USAGE = Gauge("system_disk_usage_percent", "Disk usage percentage")
DISK_USED_BYTES = Gauge("system_disk_used_bytes", "Disk used in bytes")
DISK_TOTAL_BYTES = Gauge("system_disk_total_bytes", "Total disk in bytes")


def collect_system_metrics():
    """Collect current system metrics."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    CPU_USAGE.set(cpu_percent)

    # Memory
    memory = psutil.virtual_memory()
    MEMORY_USAGE.set(memory.percent)
    MEMORY_USED_BYTES.set(memory.used)
    MEMORY_TOTAL_BYTES.set(memory.total)

    # Disk
    disk = psutil.disk_usage("/")
    DISK_USAGE.set(disk.percent)
    DISK_USED_BYTES.set(disk.used)
    DISK_TOTAL_BYTES.set(disk.total)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "metrics-collector"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    collect_system_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/stats")
async def stats():
    """JSON stats endpoint for debugging."""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "timestamp": int(time.time()),
        "cpu": {"percent": cpu_percent},
        "memory": {
            "percent": memory.percent,
            "used_gb": round(memory.used / (1024**3), 2),
            "total_gb": round(memory.total / (1024**3), 2),
        },
        "disk": {
            "percent": disk.percent,
            "used_gb": round(disk.used / (1024**3), 2),
            "total_gb": round(disk.total / (1024**3), 2),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9835)
