import { useEffect, useRef, useState, useCallback } from 'react';
import type { AgentEvent, OrchestratorStatus } from '../types';

const ORCHESTRATOR_WS_URL = 'ws://localhost:8001/ws/events';
const RECONNECT_DELAY = 3000;
const MAX_EVENTS = 100;

export function useWebSocket() {
    const [events, setEvents] = useState<AgentEvent[]>([]);
    const [status, setStatus] = useState<OrchestratorStatus>({
        connected: false,
        activeAgent: null,
        taskInProgress: false,
    });

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<number | null>(null);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        try {
            const ws = new WebSocket(ORCHESTRATOR_WS_URL);

            ws.onopen = () => {
                console.log('[WS] Connected to orchestrator');
                setStatus(prev => ({ ...prev, connected: true }));
            };

            ws.onmessage = (event) => {
                try {
                    const data: AgentEvent = JSON.parse(event.data);

                    setEvents(prev => {
                        const newEvents = [data, ...prev].slice(0, MAX_EVENTS);
                        return newEvents;
                    });

                    // Update status based on event
                    if (data.type === 'agent_start') {
                        setStatus(prev => ({
                            ...prev,
                            activeAgent: data.agent,
                            taskInProgress: true,
                        }));
                    } else if (data.type === 'agent_end') {
                        setStatus(prev => ({
                            ...prev,
                            activeAgent: null,
                        }));
                    } else if (data.type === 'complete' || data.type === 'error') {
                        setStatus(prev => ({
                            ...prev,
                            activeAgent: null,
                            taskInProgress: false,
                        }));
                    }
                } catch (e) {
                    console.error('[WS] Failed to parse message:', e);
                }
            };

            ws.onclose = () => {
                console.log('[WS] Disconnected, reconnecting...');
                setStatus(prev => ({ ...prev, connected: false }));

                // Schedule reconnect
                reconnectTimeoutRef.current = window.setTimeout(() => {
                    connect();
                }, RECONNECT_DELAY);
            };

            ws.onerror = (error) => {
                console.error('[WS] Error:', error);
            };

            wsRef.current = ws;
        } catch (e) {
            console.error('[WS] Failed to connect:', e);
        }
    }, []);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
        }
        wsRef.current?.close();
    }, []);

    const clearEvents = useCallback(() => {
        setEvents([]);
    }, []);

    useEffect(() => {
        connect();
        return () => disconnect();
    }, [connect, disconnect]);

    return {
        events,
        status,
        clearEvents,
        reconnect: connect,
    };
}
