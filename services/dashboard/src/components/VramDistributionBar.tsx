import './VramDistributionBar.css';

interface VramDistributionBarProps {
    modelBytes: number;
    cacheBytes: number;
    totalBytes: number;
}

function formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    const gb = bytes / (1024 ** 3);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 ** 2);
    return `${mb.toFixed(0)} MB`;
}

export function VramDistributionBar({ modelBytes, cacheBytes, totalBytes }: VramDistributionBarProps) {
    const total = totalBytes || 1; // Avoid division by zero
    const modelPercent = (modelBytes / total) * 100;
    const cachePercent = (cacheBytes / total) * 100;
    const freePercent = Math.max(0, 100 - modelPercent - cachePercent);

    return (
        <div className="vram-distribution">
            <div className="vram-header">
                <span className="vram-label">VRAM</span>
                <span className="vram-total">{formatBytes(modelBytes + cacheBytes)} / {formatBytes(totalBytes)}</span>
            </div>
            <div className="vram-bar">
                <div
                    className="vram-segment vram-model"
                    style={{ width: `${modelPercent}%` }}
                    title={`Model: ${formatBytes(modelBytes)}`}
                />
                <div
                    className="vram-segment vram-cache"
                    style={{ width: `${cachePercent}%` }}
                    title={`KV Cache: ${formatBytes(cacheBytes)}`}
                />
                <div
                    className="vram-segment vram-free"
                    style={{ width: `${freePercent}%` }}
                />
            </div>
            <div className="vram-legend">
                <span className="legend-item">
                    <span className="legend-dot model" />
                    Model
                </span>
                <span className="legend-item">
                    <span className="legend-dot cache" />
                    Cache
                </span>
            </div>
        </div>
    );
}
