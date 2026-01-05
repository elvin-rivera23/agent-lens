"""
AgentLens GPU Metrics Module
Collects GPU telemetry via NVML with graceful fallback
"""

import logging
import os

from prometheus_client import Gauge, Info

logger = logging.getLogger(__name__)

# GPU availability indicator
GPU_AVAILABLE = Gauge("gpu_available", "Whether GPU is available (1=yes, 0=no)")
GPU_COUNT = Gauge("gpu_count", "Number of GPUs detected")

# Per-GPU metrics (labeled by gpu_index)
GPU_UTILIZATION = Gauge(
    "gpu_utilization_percent", "GPU core utilization percentage", ["gpu_index"]
)
GPU_MEMORY_USED = Gauge(
    "gpu_memory_used_bytes", "GPU memory used in bytes", ["gpu_index"]
)
GPU_MEMORY_TOTAL = Gauge(
    "gpu_memory_total_bytes", "GPU memory total in bytes", ["gpu_index"]
)
GPU_MEMORY_PERCENT = Gauge(
    "gpu_memory_usage_percent", "GPU memory usage percentage", ["gpu_index"]
)
GPU_TEMPERATURE = Gauge(
    "gpu_temperature_celsius", "GPU temperature in Celsius", ["gpu_index"]
)
GPU_POWER = Gauge("gpu_power_watts", "GPU power consumption in watts", ["gpu_index"])
GPU_INFO = Info("gpu", "GPU device information", ["gpu_index"])

# Module state
_nvml_initialized: bool = False
_nvml_available: bool = False
_simulate_mode: bool = os.environ.get("GPU_SIMULATE", "").lower() in ("true", "1", "yes")


def _init_nvml() -> bool:
    """Initialize NVML library. Returns True if successful."""
    global _nvml_initialized, _nvml_available

    if _nvml_initialized:
        return _nvml_available

    _nvml_initialized = True

    # Simulation mode for development without GPU
    if _simulate_mode:
        logger.info("GPU simulation mode enabled")
        _nvml_available = True
        GPU_AVAILABLE.set(1)
        GPU_COUNT.set(1)
        return True

    try:
        import pynvml

        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        _nvml_available = device_count > 0

        if _nvml_available:
            GPU_AVAILABLE.set(1)
            GPU_COUNT.set(device_count)
            logger.info(f"NVML initialized: {device_count} GPU(s) detected")

            # Set GPU info labels
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                GPU_INFO.labels(gpu_index=str(i)).info({"name": name, "index": str(i)})
        else:
            GPU_AVAILABLE.set(0)
            GPU_COUNT.set(0)
            logger.info("NVML initialized but no GPUs found")

        return _nvml_available

    except ImportError:
        logger.warning("pynvml not installed - GPU metrics disabled")
        GPU_AVAILABLE.set(0)
        GPU_COUNT.set(0)
        return False
    except Exception as e:
        logger.warning(f"NVML initialization failed: {e}")
        GPU_AVAILABLE.set(0)
        GPU_COUNT.set(0)
        return False


def _collect_simulated_metrics():
    """Generate simulated GPU metrics for development."""
    import random
    import time

    # Simulate realistic-looking metrics
    base_util = 45 + 20 * (0.5 + 0.5 * (time.time() % 10) / 10)
    GPU_UTILIZATION.labels(gpu_index="0").set(min(100, base_util + random.uniform(-5, 5)))
    GPU_MEMORY_USED.labels(gpu_index="0").set(int(6.5 * 1024**3))  # 6.5 GB
    GPU_MEMORY_TOTAL.labels(gpu_index="0").set(int(12 * 1024**3))  # 12 GB
    GPU_MEMORY_PERCENT.labels(gpu_index="0").set(54.2)
    GPU_TEMPERATURE.labels(gpu_index="0").set(62 + random.uniform(-2, 2))
    GPU_POWER.labels(gpu_index="0").set(185 + random.uniform(-10, 10))


def collect_gpu_metrics():
    """Collect current GPU metrics. Safe to call even without GPU."""
    if not _init_nvml():
        return

    if _simulate_mode:
        _collect_simulated_metrics()
        return

    try:
        import pynvml

        device_count = pynvml.nvmlDeviceGetCount()

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            idx = str(i)

            # Utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                GPU_UTILIZATION.labels(gpu_index=idx).set(util.gpu)
            except pynvml.NVMLError:
                pass

            # Memory
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
                GPU_MEMORY_USED.labels(gpu_index=idx).set(mem.used)
                GPU_MEMORY_TOTAL.labels(gpu_index=idx).set(mem.total)
                GPU_MEMORY_PERCENT.labels(gpu_index=idx).set(
                    (mem.used / mem.total) * 100 if mem.total > 0 else 0
                )
            except pynvml.NVMLError:
                pass

            # Temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
                GPU_TEMPERATURE.labels(gpu_index=idx).set(temp)
            except pynvml.NVMLError:
                pass

            # Power
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle)  # milliwatts
                GPU_POWER.labels(gpu_index=idx).set(power / 1000.0)  # convert to watts
            except pynvml.NVMLError:
                pass

    except Exception as e:
        logger.error(f"Error collecting GPU metrics: {e}")


def shutdown_nvml():
    """Shutdown NVML library."""
    global _nvml_initialized, _nvml_available

    if _nvml_available and not _simulate_mode:
        try:
            import pynvml

            pynvml.nvmlShutdown()
            logger.info("NVML shutdown complete")
        except Exception as e:
            logger.warning(f"NVML shutdown error: {e}")

    _nvml_initialized = False
    _nvml_available = False
