from __future__ import annotations
import json, os, ntpath
from .redaction import redact
from .schema import Event, now_iso, stable_id

def _event(source, agent, kind, payload, **kw):
    return Event(1, str(payload.get("event_id") or stable_id(payload)), source, agent, kind, payload.get("occurred_at", now_iso()), message_excerpt=redact(str(kw.get("message", payload.get("message") or payload.get("message_excerpt") or ""))), project_name=kw.get("project_name", payload.get("project_name")), project_path=kw.get("project_path", payload.get("project_path")), session_id=kw.get("session_id", payload.get("session_id")), turn_id=kw.get("turn_id", payload.get("turn_id")), is_subagent=payload.get("is_subagent"), duration_seconds=payload.get("duration_seconds"), metadata={})

def codex(payload: dict) -> Event:
    if payload.get("type") not in ("agent-turn-complete", "agent_turn_complete"): raise ValueError("Codex notify only supports agent-turn-complete")
    project_path = payload.get("project_path", payload.get("cwd"))
    project_name = payload.get("project_name") or (ntpath.basename(str(project_path).rstrip("\\/")) if project_path else None)
    return _event("codex", "Codex", "task.completed", payload, session_id=payload.get("session_id", payload.get("thread-id")), turn_id=payload.get("turn_id", payload.get("turn-id")), project_path=project_path, project_name=project_name, message=payload.get("last-assistant-message", payload.get("message") or payload.get("message_excerpt") or ""))

def opencode(payload: dict) -> Event:
    kind = {"session.idle":"task.completed", "session.error":"task.failed", "permission.asked":"permission.required"}.get(payload.get("type"))
    if not kind: raise ValueError("unsupported OpenCode event")
    return _event("opencode", "OpenCode", kind, payload)

def claude(payload: dict) -> Event:
    kind = {"Stop":"task.completed", "StopFailure":"task.failed", "PermissionRequest":"permission.required", "PostToolUseFailure":"task.failed"}.get(payload.get("hook_event_name") or payload.get("event"))
    if not kind: raise ValueError("unsupported Claude hook event")
    return _event("claude_code", "Claude Code", kind, payload)

def parse_json(text: str) -> dict:
    value = json.loads(text)
    if not isinstance(value, dict): raise ValueError("payload must be an object")
    return value
