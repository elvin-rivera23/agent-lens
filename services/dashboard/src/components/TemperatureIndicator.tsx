import './TemperatureIndicator.css';

interface TemperatureIndicatorProps {
    temperature: number; // Celsius
}

function getTemperatureLevel(temp: number): 'cool' | 'warm' | 'hot' {
    if (temp < 60) return 'cool';
    if (temp < 80) return 'warm';
    return 'hot';
}

export function TemperatureIndicator({ temperature }: TemperatureIndicatorProps) {
    const level = getTemperatureLevel(temperature);
    const displayTemp = temperature > 0 ? `${Math.round(temperature)}°` : '—';

    return (
        <div className={`temperature-indicator temp-${level}`}>
            <div className="temp-icon">🌡️</div>
            <div className="temp-content">
                <span className="temp-label">TEMP</span>
                <span className="temp-value">{displayTemp}</span>
            </div>
        </div>
    );
}
