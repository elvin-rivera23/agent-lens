import { Brain, Code, Search, Play, CheckCircle, XCircle, RotateCcw } from 'lucide-react';
import './AgentTimeline.css';

interface Agent {
    id: string;
    name: string;
    icon: React.ReactNode;
    color: string;
    status: 'idle' | 'active' | 'complete' | 'error';
    lastAction?: string;
}

interface AgentTimelineProps {
    activeAgent: string | null;
}

const agents: Agent[] = [
    { id: 'architect', name: 'ARCHITECT', icon: <Brain size={20} />, color: 'var(--color-magenta)', status: 'idle' },
    { id: 'coder', name: 'CODER', icon: <Code size={20} />, color: 'var(--color-cyan)', status: 'idle' },
    { id: 'reviewer', name: 'REVIEWER', icon: <Search size={20} />, color: 'var(--color-orange)', status: 'idle' },
    { id: 'executor', name: 'EXECUTOR', icon: <Play size={20} />, color: 'var(--color-green)', status: 'idle' },
];

function getAgentStatus(agent: Agent, activeAgent: string | null): Agent['status'] {
    if (activeAgent === agent.id) return 'active';
    return agent.status;
}

export function AgentTimeline({ activeAgent }: AgentTimelineProps) {
    return (
        <div className="card agent-timeline">
            <div className="card-header">
                <RotateCcw size={14} />
                <span>AGENT PIPELINE</span>
            </div>

            <div className="timeline-container">
                {agents.map((agent, idx) => {
                    const status = getAgentStatus(agent, activeAgent);

                    return (
                        <div key={agent.id} className="timeline-row">
                            <div
                                className={`agent-node ${status}`}
                                style={{ '--agent-color': agent.color } as React.CSSProperties}
                            >
                                <div className="agent-icon">{agent.icon}</div>
                                <div className="agent-info">
                                    <span className="agent-name">{agent.name}</span>
                                    <span className="agent-status-text">
                                        {status === 'active' && 'PROCESSING...'}
                                        {status === 'complete' && 'DONE'}
                                        {status === 'error' && 'FAILED'}
                                        {status === 'idle' && 'STANDBY'}
                                    </span>
                                </div>
                                <div className="status-indicator">
                                    {status === 'active' && <div className="pulse-ring" />}
                                    {status === 'complete' && <CheckCircle size={16} color="var(--color-green)" />}
                                    {status === 'error' && <XCircle size={16} color="var(--color-red)" />}
                                </div>
                            </div>

                            {idx < agents.length - 1 && (
                                <div className="timeline-connector">
                                    <div className="connector-line" />
                                    <div className="connector-arrow">▼</div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
