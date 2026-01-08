import './GpuGauge.css';

interface GpuGaugeProps {
    label: string;
    value: number; // 0-100
    unit?: string;
    color?: 'cyan' | 'magenta' | 'orange' | 'green';
}

export function GpuGauge({ label, value, unit = '%', color = 'cyan' }: GpuGaugeProps) {
    const clampedValue = Math.min(100, Math.max(0, value));
    const rotation = (clampedValue / 100) * 180;

    return (
        <div className={`gpu-gauge gpu-gauge--${color}`}>
            <div className="gauge-arc">
                <svg viewBox="0 0 100 50" className="gauge-svg">
                    {/* Background arc */}
                    <path
                        d="M 10 50 A 40 40 0 0 1 90 50"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="6"
                        className="gauge-bg"
                    />
                    {/* Value arc */}
                    <path
                        d="M 10 50 A 40 40 0 0 1 90 50"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="6"
                        strokeLinecap="round"
                        className="gauge-fill"
                        style={{
                            strokeDasharray: `${(clampedValue / 100) * 126}, 126`,
                        }}
                    />
                </svg>
                {/* Needle */}
                <div
                    className="gauge-needle"
                    style={{ transform: `rotate(${rotation - 90}deg)` }}
                />
                {/* Center value */}
                <div className="gauge-value">
                    <span className="gauge-number">{Math.round(clampedValue)}</span>
                    <span className="gauge-unit">{unit}</span>
                </div>
            </div>
            <div className="gauge-label">{label}</div>
        </div>
    );
}
