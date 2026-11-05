from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib, json

EVENT_TYPES = {"task.started", "task.completed", "task.failed", "permission.required", "agent.notice"}

@dataclass(frozen=True)
class Event:
    schema_version: int
    event_id: str
    source: str
    agent_name: str
    event_type: str
    occurred_at: str
    session_id: str | None = None
    turn_id: str | None = None
    project_name: str | None = None
    project_path: str | None = None
    is_subagent: bool | None = None
    message_excerpt: str = ""
    duration_seconds: float | None = None
    metadata: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1 or not self.event_id or not self.source or not self.agent_name or self.event_type not in EVENT_TYPES:
            raise ValueError("invalid canonical event")
        if len(self.message_excerpt) > 1000 or self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("event bounds exceeded")

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), ensure_ascii=False)

def stable_id(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
