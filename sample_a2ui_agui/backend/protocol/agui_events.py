"""
AG-UI Protocol Event Definitions
Standardized lightweight, event-based schemas for Agent-User Interaction.
"""
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field
import time
import json


class AGUIEvent(BaseModel):
    """Base class for all AG-UI protocol events."""
    event: str
    timestamp: float = Field(default_factory=time.time)

    def to_sse(self) -> str:
        """Formats the event as a Server-Sent Events (SSE) data frame."""
        payload = self.model_dump()
        return f"event: {self.event}\ndata: {json.dumps(payload)}\n\n"


class RunStartedEvent(AGUIEvent):
    event: Literal["RunStartedEvent"] = "RunStartedEvent"
    run_id: str
    agent_id: str
    prompt: Optional[str] = None


class RunFinishedEvent(AGUIEvent):
    event: Literal["RunFinishedEvent"] = "RunFinishedEvent"
    run_id: str
    status: Literal["completed", "failed", "cancelled"] = "completed"


class RunErrorEvent(AGUIEvent):
    event: Literal["RunErrorEvent"] = "RunErrorEvent"
    run_id: str
    error_message: str
    error_code: Optional[str] = None


class TextMessageStartEvent(AGUIEvent):
    event: Literal["TextMessageStartEvent"] = "TextMessageStartEvent"
    message_id: str
    role: Literal["assistant", "system"] = "assistant"


class TextMessageContentEvent(AGUIEvent):
    event: Literal["TextMessageContentEvent"] = "TextMessageContentEvent"
    message_id: str
    delta: str


class TextMessageEndEvent(AGUIEvent):
    event: Literal["TextMessageEndEvent"] = "TextMessageEndEvent"
    message_id: str


class ToolCallStartEvent(AGUIEvent):
    event: Literal["ToolCallStartEvent"] = "ToolCallStartEvent"
    tool_call_id: str
    tool_name: str


class ToolCallEndEvent(AGUIEvent):
    event: Literal["ToolCallEndEvent"] = "ToolCallEndEvent"
    tool_call_id: str
    tool_name: str
    result: Any


class CustomEvent(AGUIEvent):
    """Used to transport A2UI payloads over the AG-UI pipe."""
    event: Literal["CustomEvent"] = "CustomEvent"
    custom_type: str  # e.g., "a2ui:createSurface", "a2ui:updateComponents", "a2ui:updateDataModel"
    data: Dict[str, Any]


class StateDeltaEvent(AGUIEvent):
    """Bidirectional state patch (RFC 6902 JSON Patch)."""
    event: Literal["StateDeltaEvent"] = "StateDeltaEvent"
    surface_id: str
    patches: List[Dict[str, Any]]
