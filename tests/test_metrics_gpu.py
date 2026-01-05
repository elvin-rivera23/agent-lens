"""
Tests for GPU metrics module
"""

import os
import sys
from pathlib import Path

# Add the metrics src directory to path for imports at test time
_METRICS_SRC = Path(__file__).parent.parent / "services" / "metrics" / "src"


class TestGPUMetricsSimulation:
    """Test GPU metrics in simulation mode."""

    def test_simulation_mode_collects_metrics(self):
        """Test that simulation mode generates fake GPU metrics."""
        # Add path and set simulation mode before import
        if str(_METRICS_SRC) not in sys.path:
            sys.path.insert(0, str(_METRICS_SRC))
        os.environ["GPU_SIMULATE"] = "true"

        # Import fresh (metrics are created on import)
        from gpu import _init_nvml, collect_gpu_metrics, shutdown_nvml

        # Should initialize successfully in sim mode
        result = _init_nvml()
        assert result is True

        # Collect metrics should work without error
        collect_gpu_metrics()

        # Cleanup
        shutdown_nvml()
        os.environ.pop("GPU_SIMULATE", None)


class TestGPUMetricsNoGPU:
    """Test GPU metrics behavior when no GPU is available."""

    def test_collect_metrics_safe_when_no_gpu(self):
        """Test that collect_gpu_metrics is safe to call without GPU."""
        if str(_METRICS_SRC) not in sys.path:
            sys.path.insert(0, str(_METRICS_SRC))
        os.environ.pop("GPU_SIMULATE", None)

        from gpu import collect_gpu_metrics

        # This should not raise any exceptions
        collect_gpu_metrics()


class TestGPUMetricsWithMockedNVML:
    """Test GPU metrics with mocked NVML library."""

    def test_nvml_initialization_called(self):
        """Test that NVML is properly initialized."""
        if str(_METRICS_SRC) not in sys.path:
            sys.path.insert(0, str(_METRICS_SRC))
        os.environ.pop("GPU_SIMULATE", None)

        # Import the module
        import gpu

        # Reset state for clean test
        gpu._nvml_initialized = False

        # Call init - it will either succeed or gracefully fail
        # depending on whether pynvml is installed and GPU is available
        result = gpu._init_nvml()

        # Either way, it should be marked as initialized
        assert gpu._nvml_initialized is True

        # Result is bool
        assert isinstance(result, bool)

    def test_shutdown_is_safe(self):
        """Test that shutdown_nvml is safe to call multiple times."""
        if str(_METRICS_SRC) not in sys.path:
            sys.path.insert(0, str(_METRICS_SRC))
        from gpu import shutdown_nvml

        # Should not raise
        shutdown_nvml()
        shutdown_nvml()  # Safe to call twice
