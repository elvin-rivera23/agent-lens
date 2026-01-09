/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react';
import { Brain, Code, Search, Play, ChevronDown } from 'lucide-react';
import './AgentMetricsCard.css';

interface AgentMetrics {
    id: string;
    name: string;
    icon: React.ReactNode;
    color: string;
    tokens: number | null;
    latency: number | null;
    status: 'idle' | 'working' | 'complete' | 'error';
    reasoningData: Record<string, unknown> | null;
}

interface AgentMetricsCardProps {
    agent: AgentMetrics;
    isActive?: boolean;
}

export function AgentMetricsCard({ agent, isActive }: AgentMetricsCardProps) {
    const [isDrawerOpen, setIsDrawerOpen] = useState(false);
    const formattedReasoning = JSON.stringify(agent.reasoningData ?? {}, null, 2);
    const drawerId = `reasoning-drawer-${agent.id}`;

    return (
        <div
            className={`agent-metrics-card ${agent.status} ${isActive ? 'active' : ''}`}
            style={{ '--agent-color': agent.color } as React.CSSProperties}
        >
            <div className="agent-metrics-icon">
                {agent.icon}
            </div>
            <div className="agent-metrics-name">{agent.name}</div>
            <div className="agent-metrics-stats">
                <div className="metric-row">
                    <span className="metric-label">TKN</span>
                    <span className="metric-value">
                        {agent.tokens === null ? '--' :
                            agent.tokens === 0 && agent.status === 'complete' ? '✓' :
                                agent.tokens === 0 ? '--' :
                                    agent.tokens}
                    </span>
                </div>
                <div className="metric-row">
                    <span className="metric-label">LAT</span>
                    <span className="metric-value">
                        {agent.latency !== null ? `${agent.latency.toFixed(1)}s` : '--'}
                    </span>
                </div>
            </div>
            <div className={`agent-metrics-status ${agent.status}`}>
                {agent.status === 'working' ? '●' : agent.status === 'complete' ? '✓' : agent.status === 'error' ? '✗' : '○'}
            </div>
            <div className="drawer-section">
                <button
                    className={`drawer-toggle ${isDrawerOpen ? 'expanded' : ''}`}
                    onClick={() => setIsDrawerOpen(prev => !prev)}
                    aria-expanded={isDrawerOpen}
                    aria-controls={drawerId}
                    type="button"
                >
                    <ChevronDown size={14} />
                </button>
                <div
                    id={drawerId}
                    className={`reasoning-drawer ${isDrawerOpen ? 'expanded' : ''}`}
                >
                    <pre>{formattedReasoning}</pre>
                </div>
            </div>
        </div>
    );
}

// Default agents configuration
export const defaultAgents: AgentMetrics[] = [
    { id: 'architect', name: 'ARCHITECT', icon: <Brain size={14} />, color: 'var(--color-magenta)', tokens: null, latency: null, status: 'idle', reasoningData: null },
    { id: 'coder', name: 'CODER', icon: <Code size={14} />, color: 'var(--color-cyan)', tokens: null, latency: null, status: 'idle', reasoningData: null },
    { id: 'reviewer', name: 'REVIEWER', icon: <Search size={14} />, color: 'var(--color-orange)', tokens: null, latency: null, status: 'idle', reasoningData: null },
    { id: 'executor', name: 'EXECUTOR', icon: <Play size={14} />, color: 'var(--color-green)', tokens: null, latency: null, status: 'idle', reasoningData: null },
];
