from __future__ import annotations
from dataclasses import dataclass, field
import time

@dataclass
class CompletionBatcher:
    debounce_seconds: float = 2
    max_wait_seconds: float = 8
    _events: dict[str, dict] = field(default_factory=dict)
    _first_at: float | None = None
    def add(self, event: dict) -> bool:
        key = str(event.get("event_id") or ":".join(str(event.get(k) or "") for k in ("source", "session_id", "turn_id", "event_type")))
        if key in self._events: return False
        now=time.monotonic()
        if self._first_at is None: self._first_at = now
        event["_received_at"] = now
        self._events[key] = event
        return True
    def ready(self, now: float | None = None) -> bool:
        if not self._events: return False
        current=now or time.monotonic(); elapsed=current-(self._first_at or current)
        last=max(float(e.get("_received_at", self._first_at or current)) for e in self._events.values())
        return elapsed >= self.max_wait_seconds or current-last >= self.debounce_seconds
    def flush(self) -> list[dict]:
        values = list(self._events.values()); self._events.clear(); self._first_at = None; return values
