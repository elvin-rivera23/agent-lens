"""
WebSocket Event Broadcasting

Real-time event streaming for Glass-Box visibility in the dashboard.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events that can be broadcast."""

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TOKEN = "token"
    CODE_WRITTEN = "code_written"
    EXECUTION = "execution"
    RETRY = "retry"
    ERROR = "error"
    COMPLETE = "complete"


@dataclass
class AgentEvent:
    """Structured event for WebSocket broadcasting."""

    type: EventType
    agent: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize event to JSON."""
        return json.dumps(
            {
                "type": self.type.value,
                "agent": self.agent,
                "data": self.data,
                "timestamp": self.timestamp,
            }
        )


class EventBroadcaster:
    """
    Manages WebSocket connections and broadcasts agent events.

    Usage:
        broadcaster = EventBroadcaster()
        await broadcaster.connect(websocket)
        await broadcaster.emit(EventType.AGENT_START, "coder", {"task": "..."})
    """

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

    async def emit(self, event_type: EventType, agent: str, data: dict | None = None) -> None:
        """
        Broadcast an event to all connected clients.

        Args:
            event_type: The type of event
            agent: Name of the agent emitting the event
            data: Optional event-specific data
        """
        event = AgentEvent(type=event_type, agent=agent, data=data or {})
        message = event.to_json()

        async with self._lock:
            # Create copy to avoid modification during iteration
            connections = self._connections.copy()

        # Send to all connections, removing failed ones
        failed = []
        for websocket in connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                failed.append(websocket)

        # Clean up failed connections
        if failed:
            async with self._lock:
                for ws in failed:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def emit_agent_start(self, agent: str, task: str) -> None:
        """Convenience method for agent start events."""
        await self.emit(EventType.AGENT_START, agent, {"task": task})

    async def emit_agent_end(self, agent: str, success: bool, duration: float) -> None:
        """Convenience method for agent end events."""
        await self.emit(EventType.AGENT_END, agent, {"success": success, "duration": duration})

    async def emit_code_written(self, agent: str, file_path: str, code_length: int) -> None:
        """Convenience method for code written events."""
        await self.emit(
            EventType.CODE_WRITTEN, agent, {"file_path": file_path, "code_length": code_length}
        )

    async def emit_execution(
        self, agent: str, success: bool, output: str, exit_code: int
    ) -> None:
        """Convenience method for execution events."""
        await self.emit(
            EventType.EXECUTION,
            agent,
            {"success": success, "output": output[:500], "exit_code": exit_code},
        )

    async def emit_error(self, agent: str, error: str) -> None:
        """Convenience method for error events."""
        await self.emit(EventType.ERROR, agent, {"error": error})


# Global broadcaster instance
broadcaster = EventBroadcaster()
