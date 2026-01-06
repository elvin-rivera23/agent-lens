/**
 * Agent Event Types from Orchestrator WebSocket
 */

export interface AgentEvent {
    type: EventType;
    agent: string;
    timestamp: string;
    data: Record<string, unknown>;
}

export type EventType =
    | 'agent_start'
    | 'agent_end'
    | 'token'
    | 'code_written'
    | 'execution'
    | 'retry'
    | 'error'
    | 'complete'
    | 'plan_created'
    | 'code_reviewed';

export interface OrchestratorStatus {
    connected: boolean;
    activeAgent: string | null;
    taskInProgress: boolean;
}

export interface MetricsData {
    cpu: number;
    memory: number;
    gpu?: {
        utilization: number;
        memory: number;
        temperature: number;
    };
    inference?: {
        tps: number;
        ttft: number;
    };
}

export interface CodeEvent {
    code: string;
    filePath: string;
    timestamp: string;
}

export interface ExecutionEvent {
    success: boolean;
    output: string;
    exitCode: number;
    timestamp: string;
}
