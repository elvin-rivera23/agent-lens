import { Terminal, Trash2 } from 'lucide-react';
import type { AgentEvent } from '../types';
import './EventStream.css';

interface EventStreamProps {
    events: AgentEvent[];
    onClear: () => void;
}

const eventColors: Record<string, string> = {
    agent_start: 'var(--color-cyan)',
    agent_end: 'var(--color-text-muted)',
    code_written: 'var(--color-green)',
    execution: 'var(--color-orange)',
    error: 'var(--color-red)',
    retry: 'var(--color-yellow)',
    complete: 'var(--color-green)',
    plan_created: 'var(--color-magenta)',
    code_reviewed: 'var(--color-cyan)',
};

const eventIcons: Record<string, string> = {
    agent_start: '▶',
    agent_end: '■',
    code_written: '📝',
    execution: '⚡',
    error: '✖',
    retry: '↻',
    complete: '✓',
    plan_created: '📋',
    code_reviewed: '🔍',
};

function formatTime(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

export function EventStream({ events, onClear }: EventStreamProps) {
    return (
        <div className="card event-stream">
            <div className="card-header">
                <Terminal size={14} />
                <span>EVENT STREAM</span>
                <button className="clear-btn" onClick={onClear} title="Clear events">
                    <Trash2 size={12} />
                </button>
            </div>

            <div className="event-list scanlines">
                {(() => {
                    // Filter out noisy events
                    const filteredEvents = events.filter(e =>
                        !['token', 'file_created', 'workspace_reset'].includes(e.type)
                    ).slice(-20);

                    console.log('[EventStream] Total events:', events.length, 'Filtered:', filteredEvents.length, 'Types:', [...new Set(events.map(e => e.type))]);

                    if (filteredEvents.length === 0) {
                        return (
                            <div className="empty-state">
                                <span className="glitch-text">AWAITING EVENTS...</span>
                            </div>
                        );
                    }

                    return filteredEvents.map((event, idx) => (
                        <div
                            key={`${event.timestamp}-${idx}`}
                            className="event-item data-stream"
                            style={{ '--event-color': eventColors[event.type] || 'var(--color-text-primary)' } as React.CSSProperties}
                        >
                            <span className="event-icon">{eventIcons[event.type] || '•'}</span>
                            <span className="event-time">{formatTime(event.timestamp)}</span>
                            <span className="event-agent">[{event.agent.toUpperCase()}]</span>
                            <span className="event-type">{event.type}</span>
                            {event.data && Object.keys(event.data).length > 0 && (
                                <span className="event-data">
                                    {JSON.stringify(event.data).slice(0, 50)}
                                    {JSON.stringify(event.data).length > 50 && '...'}
                                </span>
                            )}
                        </div>
                    ))
                })()}
            </div>
        </div>
    );
}
