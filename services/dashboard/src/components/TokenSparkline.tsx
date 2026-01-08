import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import './TokenSparkline.css';

interface DataPoint {
    time: number;
    value: number;
}

interface TokenSparklineProps {
    data: DataPoint[];
    currentTps: number;
}

export function TokenSparkline({ data, currentTps }: TokenSparklineProps) {
    // Format TPS for display
    const displayTps = currentTps > 0 ? currentTps.toFixed(1) : '—';

    return (
        <div className="token-sparkline">
            <div className="sparkline-header">
                <span className="sparkline-label">TPS</span>
                <span className="sparkline-value">{displayTps}</span>
            </div>
            <div className="sparkline-chart">
                <ResponsiveContainer width="100%" height={32}>
                    <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
                        <YAxis domain={['dataMin', 'dataMax']} hide />
                        <Line
                            type="monotone"
                            dataKey="value"
                            stroke="var(--color-green)"
                            strokeWidth={1.5}
                            dot={false}
                            isAnimationActive={false}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
