import { Wifi, WifiOff, Cpu, Activity } from 'lucide-react';
import type { OrchestratorStatus } from '../types';
import './Header.css';

interface HeaderProps {
    status: OrchestratorStatus;
    agentProgress?: number; // 0-4 (number of completed agents)
}

export function Header({ status, agentProgress = 0 }: HeaderProps) {
    const progressPercent = (agentProgress / 4) * 100;

    return (
        <header className="header">
            <div className="header-brand">
                <h1 className="glitch-text flicker">AGENT<span className="accent">LENS</span></h1>
                <span className="header-subtitle">Multi-Agent Orchestration HUD</span>
            </div>

            {/* Task Progress Bar */}
            {status.taskInProgress && (
                <div className="task-progress-container">
                    <div className="task-progress-label">
                        STAGE {agentProgress}/4
                    </div>
                    <div className="task-progress-bar">
                        <div
                            className="task-progress-fill"
                            style={{ width: `${progressPercent}%` }}
                        />
                    </div>
                </div>
            )}

            <div className="header-status">
                {status.activeAgent && (
                    <div className="active-agent pulse">
                        <Cpu size={14} />
                        <span>{status.activeAgent.toUpperCase()}</span>
                    </div>
                )}

                {status.taskInProgress && (
                    <div className="task-indicator">
                        <Activity size={14} className="spin" />
                        <span>PROCESSING</span>
                    </div>
                )}

                <div className={`connection-status ${status.connected ? 'connected' : 'disconnected'}`}>
                    {status.connected ? <Wifi size={14} /> : <WifiOff size={14} />}
                    <span>{status.connected ? 'ONLINE' : 'OFFLINE'}</span>
                </div>
            </div>
        </header>
    );
}

