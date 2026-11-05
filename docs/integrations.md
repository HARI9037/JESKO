# Integrations

Claude Code uses notification-only hook events (`Stop`, `StopFailure`, `PostToolUseFailure`, `PermissionRequest`) and pipes JSON to `jesko ingest --adapter claude --stdin`. JESKO emits no decision object and never blocks the hook. Generate/copy a user-reviewed settings snippet; it is not installed automatically.

Codex supports only the documented `agent-turn-complete` notify event, mapped to `task.completed`. Native fields map as `thread-id` → `session_id`, `turn-id` → `turn_id`, `cwd` → local-only `project_path` with its basename as `project_name`, and `last-assistant-message` → redacted `message_excerpt`. Legacy normalized aliases remain supported. It does not provide permission or error events through notify. Put the command in the user-level Codex `config.toml`, not a project config.

OpenCode's thin plugin bridge maps `session.idle`, `session.error`, and `permission.asked`; ambiguous payloads are ignored. It does not mutate event or permission state.

For Hermes, KiloCode, or another CLI without a verified hook: `jesko run --agent Name -- executable args...`. It returns the child exit code and uses `shell=False`.
