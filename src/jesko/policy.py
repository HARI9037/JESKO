from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True)
class Decision:
    push: bool; call: bool; batch: bool; reason: str
def decide(event_type: str, calls_enabled: bool, quiet: bool, notice_enabled=False) -> Decision:
    if event_type == "task.completed": return Decision(True, False, True, "completion")
    if event_type in {"task.failed", "permission.required"}: return Decision(True, calls_enabled and not quiet, False, "urgent")
    if event_type == "agent.notice": return Decision(notice_enabled, False, notice_enabled, "notice")
    return Decision(False, False, False, "start-only")
def in_quiet_hours(now: datetime, start="22:00", end="07:00") -> bool:
    t = now.strftime("%H:%M")
    return t >= start or t < end if start > end else start <= t < end
