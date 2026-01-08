/* eslint-disable react-refresh/only-export-components */
import { useState, useEffect, useRef, useCallback } from 'react';

const ORCHESTRATOR_URL = import.meta.env.VITE_ORCHESTRATOR_URL || 'http://localhost:8001';
const POLL_INTERVAL = 2000; // 2 seconds

export interface GpuMetrics {
    gpuLoad: number;           // 0-100 percentage
    vramPercent: number;       // 0-100 percentage
    vramModelBytes: number;    // Bytes used by model weights
    vramCacheBytes: number;    // Bytes used by KV cache
    vramTotalBytes: number;    // Total VRAM
    temperature: number;       // Celsius
    tokensPerSecond: number;   // Current TPS
    available: boolean;        // GPU available flag
}

interface TpsHistoryPoint {
    time: number;
    value: number;
}

const defaultMetrics: GpuMetrics = {
    gpuLoad: 0,
    vramPercent: 0,
    vramModelBytes: 0,
    vramCacheBytes: 0,
    vramTotalBytes: 0,
    temperature: 0,
    tokensPerSecond: 0,
    available: false,
};

/**
 * Parse Prometheus text format and extract metric value
 */
function parsePrometheusMetric(text: string, metricName: string, labelFilter?: string): number {
    const lines = text.split('\n');
    for (const line of lines) {
        if (line.startsWith('#')) continue;
        if (line.startsWith(metricName)) {
            // Handle labeled metrics like gpu_utilization_percent{gpu_index="0"}
            if (labelFilter && !line.includes(labelFilter)) continue;
            const match = line.match(/\s+([\d.]+)$/);
            if (match) {
                return parseFloat(match[1]);
            }
        }
    }
    return 0;
}

export function useGpuMetrics() {
    const [metrics, setMetrics] = useState<GpuMetrics>(defaultMetrics);
    const [tpsHistory, setTpsHistory] = useState<TpsHistoryPoint[]>([]);
    const [error, setError] = useState<string | null>(null);
    const lastTokenCount = useRef<number>(0);
    const lastTime = useRef<number>(Date.now());

    const fetchMetrics = useCallback(async () => {
        try {
            // Fetch from orchestrator's /metrics endpoint
            const response = await fetch(`${ORCHESTRATOR_URL}/metrics`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const text = await response.text();

            // Parse GPU metrics (gpu_index="0" for first GPU)
            const gpuLoad = parsePrometheusMetric(text, 'gpu_utilization_percent', 'gpu_index="0"');
            const vramPercent = parsePrometheusMetric(text, 'gpu_memory_usage_percent', 'gpu_index="0"');
            const vramUsed = parsePrometheusMetric(text, 'gpu_memory_used_bytes', 'gpu_index="0"');
            const vramTotal = parsePrometheusMetric(text, 'gpu_memory_total_bytes', 'gpu_index="0"');
            const temperature = parsePrometheusMetric(text, 'gpu_temperature_celsius', 'gpu_index="0"');
            const gpuAvailable = parsePrometheusMetric(text, 'gpu_available');

            // Parse inference VRAM breakdown
            const vramModelBytes = parsePrometheusMetric(text, 'inference_vram_model_bytes');
            const vramCacheBytes = parsePrometheusMetric(text, 'inference_vram_context_bytes');

            // Parse token metrics for TPS calculation
            const totalTokens = parsePrometheusMetric(text, 'inference_tokens_total') ||
                parsePrometheusMetric(text, 'orchestrator_tokens_generated_total');

            // Calculate tokens per second
            const now = Date.now();
            const timeDelta = (now - lastTime.current) / 1000;
            const tokenDelta = totalTokens - lastTokenCount.current;
            const tps = timeDelta > 0 && lastTokenCount.current > 0
                ? Math.max(0, tokenDelta / timeDelta)
                : 0;

            lastTokenCount.current = totalTokens;
            lastTime.current = now;

            setMetrics({
                gpuLoad,
                vramPercent,
                vramModelBytes,
                vramCacheBytes: vramCacheBytes || (vramUsed - vramModelBytes),
                vramTotalBytes: vramTotal,
                temperature,
                tokensPerSecond: tps,
                available: gpuAvailable === 1,
            });

            // Update TPS history (keep last 30 points)
            setTpsHistory(prev => {
                const newPoint = { time: now, value: tps };
                const updated = [...prev, newPoint];
                return updated.slice(-30);
            });

            setError(null);
        } catch (err) {
            // Don't spam errors - metrics endpoint may not be available in dev
            setError(err instanceof Error ? err.message : 'Unknown error');
        }
    }, []);

    useEffect(() => {
        // Initial fetch
        fetchMetrics();

        // Poll every POLL_INTERVAL ms
        const interval = setInterval(fetchMetrics, POLL_INTERVAL);

        return () => clearInterval(interval);
    }, [fetchMetrics]);

    return { metrics, tpsHistory, error };
}
