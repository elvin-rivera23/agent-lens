import { Wifi, WifiOff, Cpu, Activity } from 'lucide-react';
import type { OrchestratorStatus } from '../types';
import './Header.css';

interface HeaderProps {
    status: OrchestratorStatus;
}

export function Header({ status }: HeaderProps) {
    return (
        <header className="header">
            <div className="header-brand">
                <h1 className="glitch-text flicker">AGENT<span className="accent">LENS</span></h1>
                <span className="header-subtitle">Multi-Agent Orchestration HUD</span>
            </div>

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
