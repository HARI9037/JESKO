# JESKO Stage 1 implementation status

- [x] Standard-library-first Python package, CLI, Windows user paths, TOML/env configuration.
- [x] Canonical schema, adapters for Claude Code/Codex/OpenCode, generic non-shell wrapper.
- [x] Redaction, bounded excerpts, SQLite durable dedupe queue.
- [x] Pure routing policy, quiet-hours handling, provider interfaces for ntfy/Twilio.
- [x] Safety docs and integration snippets.
- [x] Automated tests for schema, adapters, redaction, policy, storage, providers, and wrapper.
- [ ] Live provider verification: intentionally not performed; requires user credentials and explicit commands.
- [x] Remote summarizer fallback chain with bounded redacted input and local template fallback.
- [x] SQLite WAL mode, bounded recovery attempts, retention cleanup, and safe test-call dry run.
- [ ] Full provider-backed worker integration and long-task timer remain deployment verification items.
- [x] Unified worker orchestration, atomic claims, bounded retries, dead-letter state, cooldown persistence, urgent bypass, and safe CLI worker modes.
- [x] Ten automated tests pass with mocked/no external delivery.
- [x] Dry-run is read-only; one-shot and shutdown flush completion batches with per-event status updates; provider outcomes are isolated.
- [x] Worker lifecycle acceptance tests: 14 passed, including dry-run immutability, one-shot delivery, shutdown failure preservation, restart claim recovery coverage, and independent ntfy/Twilio outcomes.
- [x] Native Codex `agent-turn-complete` payload mapping and legacy alias compatibility, covered by adapter and deduplication tests.

This is Stage 1 only. JESKO has no remote control, public server, conversational voice path, or arbitrary command execution from notifications.
