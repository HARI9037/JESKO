# JESKO — Stage 1 Product Requirements & Build Plan

> **Product:** JESKO  
> **Full form:** To be supplied by the creator — intentionally left undecided.  
> **Document version:** 0.1  
> **Date:** 31 October 2026  
> **Status:** Draft for implementation with Codex  
> **Stage:** 1 — One-way agent notifications and spoken alerts

---

## 1. Executive summary

JESKO is a local-first notification companion for AI coding agents running on the user's laptop. It listens to lifecycle events emitted by supported agents, converts those events into a small, privacy-filtered notification, and delivers the notification through:

1. **ntfy push notifications** for normal completion events.
2. **Automated phone calls** for configured urgent events such as permission requests, failures, and long-running tasks.

The initial release is deliberately a **notification system with one-way spoken alerts**, not a conversational voice assistant. JESKO will not control coding agents, approve tools, run arbitrary commands in response to a call, or expose a remote shell. Those capabilities are outside Stage 1.

The application runs locally on Windows. Cloud model providers are optional and used only to turn a redacted assistant result into one or two spoken sentences. When cloud summarization is disabled or unavailable, JESKO uses deterministic local templates.

### Stage 1 outcome

A coding agent emits an event → JESKO validates and redacts it → applies routing policy → batches nearby completion events → produces a short notification → sends an ntfy push and, when enabled and eligible, a Twilio voice call.

### Product principle

**Local event capture. Minimal data disclosure. Explicit alert policy. No effect on the coding agent's execution.**

---

## 2. Review of the original design proposal

The Claude proposal has a sound high-level direction: local hooks, a single event-ingestion entry point, a policy layer, ntfy for push, Twilio for calls, summarizer fallbacks, deduplication, and a later conversational Stage 2.

A few details need to be tightened before implementation:

| Original assumption | Design correction |
|---|---|
| A 30-second batch window and a notification within about 10 seconds | These conflict. Stage 1 uses a short debounce (default 2 seconds) and a maximum batch wait (default 8 seconds). Urgent events bypass batching. The latency target is best-effort, not a hard guarantee. |
| Codex can report completion, permission, and error events through `notify` | Current Codex documentation says `notify` currently emits only `agent-turn-complete`. JESKO must not pretend it can receive permission/error events through that interface. A process wrapper can additionally observe the exit code when the user launches Codex through it. |
| All integrations have equivalent hooks | They do not. Each adapter must map only events the source actually exposes. Unsupported event classes must be documented, not inferred. |
| Twilio trial calls are available for a fixed 30-day period | Do not hard-code a trial duration or promise trial behavior. Read the current account restrictions in the Twilio Console. |
| Twilio can straightforwardly call an Indian mobile number | Twilio's published India Voice Guidelines list domestic outbound calling as unavailable and international outbound calling as available, subject to restrictions. A +91 destination therefore needs account/provider eligibility checked before enabling calls. |
| Any hook can safely be detached and always return success | This is valid only for notification-only handlers. JESKO must never change a permission decision or block/continue an agent turn. Hook adapters should be non-blocking and fail open. |
| Cloud summarization can be the default | Cloud summarization is opt-in. Raw transcripts are never sent. Only a short, redacted assistant-result excerpt and minimal metadata may be sent when explicitly enabled. |

**Important:** Stage 1 does not use Grok Voice Agent Builder. It uses Twilio's outbound call capability for a short, one-way spoken alert. Grok Voice Agent Builder or Pipecat may be evaluated for a later conversational version, but neither is a Stage 1 dependency.

---

## 3. Product vision and objectives

### Vision

Make it possible to step away from the laptop without losing awareness of important coding-agent activity.

### Primary objectives

- Capture agent completion, failure, and approval-needed events where the source provides them.
- Deliver concise, non-sensitive push notifications.
- Place a short outbound voice call for configured urgent events when telephony is enabled and supported.
- Combine bursts of completion events into one notification.
- Prevent notification failures from breaking or delaying coding-agent work.
- Keep secrets, full transcripts, source code, and full project paths out of outbound notifications.
- Work locally on Windows without requiring a public application server.

### Success criteria

- A synthetic completion event reaches a configured ntfy topic.
- A real supported agent completion event produces a push notification under normal network conditions, targeted within 10 seconds.
- A synthetic urgent event selects the call route; with telephony enabled and provider eligibility verified, the call is placed.
- Five completion events received in one short burst become one batched push.
- Duplicate hook delivery does not create duplicate notifications.
- Provider failure does not change an agent's exit code or interrupt its execution.
- All automated tests pass without requiring real API keys or making real phone calls.

---

## 4. Target user and primary use case

### Primary user

A developer running several AI coding agents locally and wanting low-friction awareness while away from the screen.

### Main use case

The user starts a task in Claude Code, Codex, OpenCode, or another supported CLI. JESKO receives the agent's event, prepares a short status message, and sends the correct alert without requiring the user to keep the terminal in focus.

### Example notifications

- Push: “Codex finished working on FoodFlow.”
- Push: “Claude Code completed a task in Samaktha. Five agent updates were grouped.”
- Voice: “JESKO alert. Claude Code is waiting for your permission.”
- Voice: “JESKO alert. An agent task failed in the current project.”

Messages must not include code, secrets, raw prompts, full file paths, stack traces, or full transcripts.

---

## 5. Scope

### In scope — Stage 1

1. Local JESKO CLI and worker process.
2. Canonical event schema and source adapters.
3. SQLite event queue, deduplication, retry state, and cooldown state.
4. Secret redaction and safe notification formatting.
5. Optional summarization provider chain: NVIDIA NIM → OpenRouter → local template.
6. ntfy push provider.
7. Twilio outbound voice-call provider behind an explicit feature flag.
8. Routing policy, quiet hours, cooldowns, batching, and long-task detection for adapters that provide task-start events.
9. Initial adapters for:
   - Claude Code hooks.
   - Codex `notify` completion events.
   - OpenCode plugin events.
   - Generic command wrapper for tools without a reliable event hook, including possible Hermes/KiloCode use.
10. Test fixtures, automated tests, configuration examples, setup instructions, and diagnostics.

### Explicitly out of scope — Stage 1

- Two-way phone conversation.
- Speech recognition or conversational TTS streaming.
- Pipecat, FastAPI, Cloudflare Tunnel, or a publicly reachable JESKO server.
- Grok Voice Agent Builder integration.
- Starting, stopping, steering, or delegating tasks to coding agents.
- Approving or denying agent permission requests remotely.
- Arbitrary shell execution from a phone call, push action, or webhook.
- Reading full agent transcripts or project source files.
- Multi-user accounts, hosted dashboards, cloud sync, or team administration.
- Guaranteed event coverage for agents whose current integration does not expose the required events.

---

## 6. Functional requirements

### FR-01 — Event ingestion

JESKO must accept event payloads from different agent adapters through one canonical ingestion interface.

Supported ingestion modes:

- JSON from standard input (Claude Code hooks).
- JSON passed as a command-line argument (Codex `notify`).
- JSON emitted by the OpenCode plugin bridge.
- JESKO's own process wrapper for tools that do not provide a supported hook.
- Synthetic JSON fixture for testing.

Every adapter must validate its payload and produce a canonical JESKO event. Malformed payloads must be logged as a metadata-only warning and ignored safely.

### FR-02 — Canonical event model

Each event should contain, where available:

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "source": "claude_code",
  "agent_name": "Claude Code",
  "event_type": "task.completed",
  "occurred_at": "2026-10-31T09:30:00Z",
  "session_id": "source-session-id",
  "turn_id": "source-turn-id",
  "project_name": "Samaktha",
  "project_path": "C:/Projects/Samaktha",
  "is_subagent": false,
  "message_excerpt": "Completed the implementation and tests passed.",
  "duration_seconds": 125,
  "metadata": {}
}
```

Rules:

- `event_type` must be one of `task.started`, `task.completed`, `task.failed`, `permission.required`, or `agent.notice`.
- Optional source fields may be absent; adapters must not invent them.
- `project_name` is the basename only. Full paths stay local and are not included in outbound messages.
- `message_excerpt` must be redacted and length-limited before it is stored or transmitted.
- Raw hook payloads and full transcripts must not be persisted.
- Unknown event types must be rejected or normalized to `agent.notice` only when the adapter can safely justify that mapping.

### FR-03 — Policy and routing

Default policy:

| Event | Default channel | Batching | Notes |
|---|---|---|---|
| `task.completed` | ntfy push | Yes | Group nearby completions. |
| `permission.required` | Twilio call + ntfy fallback | No | Calls are disabled until explicitly enabled. |
| `task.failed` | Twilio call + ntfy fallback | No | Calls are disabled until explicitly enabled. |
| Long-running task threshold reached | Twilio call + ntfy fallback | No | Only for adapters that provide a reliable start event. |
| `task.started` | No alert | N/A | Stored only to track duration. |
| `agent.notice` | ntfy push only when explicitly configured | Yes | Avoid noisy alerts by default. |

The policy layer must be deterministic and separately unit-tested. It must not invoke any coding-agent tool or alter the event source's permission state.

### FR-04 — Batching and deduplication

- Default completion debounce: 2 seconds.
- Default maximum batch wait: 8 seconds from the first pending completion.
- Urgent events bypass batching.
- Dedupe key: source + session identifier + turn/event identifier + event type, falling back to a stable payload hash when source identifiers are unavailable.
- Ignore subagent events by default only when the adapter can positively identify them. Do not suppress normal events based on guesses.
- A cooldown must prevent repetitive calls for the same source/session. Default urgent cooldown: 15 minutes.

### FR-05 — Long-task detection

- Default threshold: 10 minutes.
- Only create a long-task timer when an adapter emits a trustworthy `task.started` event.
- Send at most one long-task alert per session until a completion/failure event closes the task.
- The Codex `notify` adapter cannot determine task duration from the completion-only event by itself. The optional JESKO process wrapper can track elapsed time when Codex is launched through that wrapper.
- Missing completion events must not create unbounded repeated calls.

### FR-06 — Summarization

Provider priority when cloud summarization is enabled:

1. NVIDIA NIM.
2. OpenRouter.
3. Deterministic local template.

Requirements:

- Cloud summarization is **disabled by default**.
- It must be explicitly enabled in local configuration.
- Never send raw hook JSON, user prompts, entire transcripts, code diffs, file contents, credentials, or full paths.
- Only send a short, already-redacted assistant-result excerpt (maximum 1,000 characters) plus non-sensitive metadata such as agent label and project basename.
- Use a total summarization time budget of 4 seconds, with no retry loop. If the first provider is unavailable or times out, try the next provider only within the remaining budget; otherwise use a local template.
- The returned text must be 1–2 short sentences, suitable for speech, without code, paths, secrets, or unsupported claims.
- Treat model output as untrusted text: apply redaction and length limits again after generation.

### FR-07 — ntfy provider

- Support configurable server URL and topic.
- Support optional bearer token authentication.
- Use HTTPS unless the user explicitly configures a local trusted endpoint.
- Include notification title, message, priority, and tags where supported.
- Do not publish secrets or sensitive project details. A topic name on the public ntfy service is effectively a bearer-like capability and must be high entropy.
- A failed push must be recorded for bounded retry and must not crash the worker.

### FR-08 — Twilio provider

- Implement an isolated provider adapter using Twilio's Calls REST API and inline TwiML `<Say>` content.
- Calls are disabled by default: `JESKO_CALLS_ENABLED=false`.
- Require `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, and `JESKO_TO_NUMBER` in local environment configuration.
- Validate phone numbers in E.164 format before attempting a call.
- Escape generated speech text before constructing TwiML.
- Set a strict call time limit (default 30 seconds) and speak only the short event message.
- On any call failure, send an ntfy fallback if ntfy is configured.
- Provide a `test-call` command that requires an explicit confirmation flag and prints the destination with partial masking before dispatch.
- Never call any number other than the configured personal destination in Stage 1.

**India deployment caveat:** Twilio's published India Voice Guidelines currently list domestic outbound calling as unavailable and international outbound calling as available only under the stated restrictions. Do not assume a standard Indian Twilio number can call a +91 mobile. Keep calls disabled until the user's Twilio Console, caller ID, destination, account, and applicable Indian telecom requirements have been checked. Do not describe this as legal advice.

### FR-09 — Configuration and secrets

- Provide a `.env.example` for documentation only; it must contain placeholders, never real credentials.
- Actual user secrets must live outside the repository, preferably in the user's JESKO configuration directory or environment variables.
- Add `.env`, local config overrides, databases, logs, and generated secrets to `.gitignore`.
- Never print secret values in logs, diagnostics, exceptions, or `jesko doctor` output.
- `jesko doctor` should report whether a required setting is present, not its value.

### FR-10 — Non-interference

- Hook handlers must be notification-only and fail open.
- They must not block, approve, deny, or modify any agent action.
- Ingestion should return quickly after durably queuing a sanitized event.
- Provider/network failure must not change an agent's exit code.
- Background processing must be separate from the source agent process.

### FR-11 — Diagnostics and testability

Provide:

- `jesko init` — create user config/data directories and safe default config.
- `jesko doctor` — validate paths and configuration presence without exposing secrets.
- `jesko worker` — run the local queue worker in the foreground.
- `jesko ingest --adapter <name> --stdin` — ingest JSON from stdin.
- `jesko codex-notify <json>` — parse Codex's JSON command-line argument.
- `jesko simulate <fixture>` — feed a known fixture into the pipeline.
- `jesko test-push` — send a non-sensitive test push.
- `jesko test-call --confirm` — explicitly place a test call when enabled.
- `jesko run --agent <name> -- <command> [args...]` — optionally wrap a process, publish start/end events, and preserve the child's exit code.

The default development/test workflow must use fake providers. Tests must never send real push notifications or phone calls unless a developer deliberately runs an explicit live-test command.

---

## 7. Non-functional requirements

### Reliability

- SQLite-backed queue so an event is not lost merely because the worker is briefly unavailable.
- Bounded retries with exponential backoff for transient provider failures.
- Worker restart must recover pending events.
- Use SQLite transactions and a unique dedupe constraint.

### Performance

- Ingestion target: under 250 ms for local validation, redaction, and queueing under normal conditions.
- Completion notification target: best-effort under 10 seconds when services are reachable and cloud summarization is either disabled or completes within budget.
- Urgent events must bypass completion batching.

### Privacy

- Local-first by default.
- No telemetry or analytics in Stage 1.
- No raw transcript storage.
- Store only sanitized, bounded event details needed for delivery and dedupe.
- Provide configurable local retention; default 7 days for completed event records.

### Security

- Use TLS for remote APIs.
- Do not use `shell=True` in the process wrapper.
- Validate event type, lengths, and JSON shape.
- Escape TwiML/XML content.
- Redact common API key, bearer token, JWT, private-key, password, and cloud-token patterns.
- Keep the ntfy topic out of source control and logs.
- Never expose a local HTTP server or public tunnel in Stage 1.

### Maintainability

- Small, modular Python codebase.
- Python 3.11+.
- Standard-library-first implementation; only add focused dependencies where justified.
- Type hints, structured logging, clear adapter interfaces, and automated unit tests.

---

## 8. Architecture

```text
Claude Code hooks ──────┐
Codex notify ───────────┤
OpenCode plugin ────────┼──> Adapter layer
Generic run wrapper ───┘          │
                                  v
                         Validate + normalize
                                  │
                                  v
                         Secret redaction
                                  │
                                  v
                       SQLite event/outbox queue
                                  │
                                  v
                           JESKO worker
                                  │
                  ┌───────────────┴────────────────┐
                  v                                v
            Policy + cooldown                Batch scheduler
                  │                                │
                  └───────────────┬────────────────┘
                                  v
                         Safe message builder
                                  │
                   Optional summarizer chain
                   NVIDIA → OpenRouter → template
                                  │
                  ┌───────────────┴────────────────┐
                  v                                v
             ntfy push                       Twilio call
                                         (feature-flagged)
```

### Component boundaries

- **Adapters:** Understand source-specific payloads and map them to canonical events. No provider API calls.
- **Ingestion service:** Validate, redact, deduplicate, and persist events. No LLM call.
- **Policy engine:** Decide whether, when, and where to alert. Pure deterministic logic.
- **Worker:** Batch, detect timeouts, call summarizer, and dispatch notifications.
- **Providers:** ntfy, Twilio, NVIDIA NIM, and OpenRouter. Each provider must be replaceable and mockable.
- **CLI:** User-facing commands and diagnostics.

---

## 9. Agent integration capability matrix

Do not promise the same event coverage for every agent. Build and document adapter capabilities explicitly.

| Agent / integration | Stage 1 mechanism | Completion | Failure | Permission needed | Start / long-task timing |
|---|---|---:|---:|---:|---:|
| Claude Code | Command hooks | Yes (`Stop`) | Yes (`StopFailure`, `PostToolUseFailure`) | Yes (`PermissionRequest` or permission notification event) | Yes (`UserPromptSubmit` or session lifecycle, with careful task correlation) |
| Codex CLI | User-level `notify` command | Yes (`agent-turn-complete`) | Not through `notify` as currently documented | Not through `notify` as currently documented | Not through `notify` alone; generic wrapper can measure process duration |
| OpenCode | Plugin event API | Yes (`session.idle`) | Yes (`session.error`) | Yes (`permission.asked`) | Session/message events; correlate conservatively |
| Hermes / KiloCode / other CLIs | `jesko run --agent <name> -- <command>` wrapper | Yes, on child exit 0 | Yes, on non-zero child exit | Not generically available | Yes, process duration only |

### Integration rules

- Claude Code's hook output must never return an approval/deny/continue decision. It is a side-effect-only notifier.
- Codex `notify` currently documents only `agent-turn-complete`; JESKO must not fabricate permission/error support for that adapter.
- OpenCode event names must be checked against the installed version. If the plugin cannot confidently interpret an event, it should ignore it and log a metadata-only diagnostic.
- The generic wrapper sees only the process it launches. It cannot observe an agent process that was launched outside it.
- Install or modify global agent configuration only after the user explicitly chooses to do so. Default behavior is to generate integration snippets and instructions, not silently edit user config files.

---

## 10. Routing policy and defaults

Suggested initial `jesko.toml` settings:

```toml
[app]
name = "JESKO"
timezone = "Asia/Kolkata"
log_level = "INFO"
retention_days = 7

[batching]
debounce_seconds = 2
max_wait_seconds = 8

[policy]
long_task_threshold_minutes = 10
urgent_cooldown_minutes = 15
ignore_subagents = true

[quiet_hours]
enabled = true
start = "22:00"
end = "07:00"
timezone = "Asia/Kolkata"
urgent_behavior = "push_only"

[summarization]
enabled = false
total_timeout_seconds = 4
max_input_chars = 1000

[ntfy]
enabled = true
server = "https://ntfy.sh"

[twilio]
enabled = false
call_time_limit_seconds = 30
```

Quiet-hours default: urgent events still produce ntfy push notifications, but phone calls are suppressed. The user can change this deliberately.

---

## 11. Configuration reference

The implementation should load settings from a user-level config file plus environment variables. Environment variables override file settings.

`.env.example` should list placeholders such as:

```dotenv
# Optional cloud summarization. Disabled unless explicitly enabled in config.
JESKO_CLOUD_SUMMARIZATION_ENABLED=false
JESKO_NVIDIA_API_KEY=
JESKO_NVIDIA_BASE_URL=
JESKO_NVIDIA_MODEL=
JESKO_OPENROUTER_API_KEY=
JESKO_OPENROUTER_MODEL=

# ntfy
JESKO_NTFY_TOPIC=
JESKO_NTFY_TOKEN=

# Twilio — keep calls disabled until regional/account eligibility is verified.
JESKO_CALLS_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
JESKO_TO_NUMBER=
```

Do not hard-code a model identifier or endpoint that may become invalid. Require the user to configure the NVIDIA model and endpoint selected from the current NVIDIA API catalog. OpenRouter should use a configured model slug.

---

## 12. Suggested repository layout

```text
jesko/
├── pyproject.toml
├── README.md
├── LICENSE                 # only if the owner chooses a license
├── .gitignore
├── .env.example
├── config/
│   └── default.toml
├── integrations/
│   ├── claude-code/
│   │   └── settings-snippet.json
│   ├── codex/
│   │   └── config-snippet.toml
│   └── opencode/
│       └── plugin.js
├── scripts/
│   ├── start-jesko.ps1
│   └── install-startup-task.ps1
├── src/
│   └── jesko/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── paths.py
│       ├── schema.py
│       ├── redaction.py
│       ├── storage.py
│       ├── ingestion.py
│       ├── policy.py
│       ├── batching.py
│       ├── worker.py
│       ├── runner.py
│       ├── logging_config.py
│       ├── adapters/
│       │   ├── base.py
│       │   ├── claude_code.py
│       │   ├── codex.py
│       │   ├── opencode.py
│       │   └── generic.py
│       ├── summarizers/
│       │   ├── base.py
│       │   ├── chain.py
│       │   ├── nvidia_nim.py
│       │   ├── openrouter.py
│       │   └── template.py
│       └── providers/
│           ├── base.py
│           ├── ntfy.py
│           └── twilio.py
├── tests/
│   ├── fixtures/
│   ├── test_schema.py
│   ├── test_redaction.py
│   ├── test_adapters.py
│   ├── test_policy.py
│   ├── test_batching.py
│   ├── test_storage.py
│   ├── test_summarizers.py
│   ├── test_ntfy.py
│   ├── test_twilio.py
│   └── test_non_interference.py
└── docs/
    ├── setup-windows.md
    ├── integrations.md
    └── security-and-privacy.md
```

Codex may adjust this layout if a simpler structure is materially better, but it must preserve the module boundaries and testability.

---

## 13. Implementation plan

### Milestone 1 — Foundation and canonical events

- Set up the Python package, CLI entry point, configuration loader, application paths, and SQLite schema.
- Define canonical event types and adapters' shared interface.
- Implement validation, normalization, redaction, and deduplication.
- Add fixtures and unit tests.

**Exit criteria:** synthetic event can be ingested and safely persisted; duplicate events are ignored; raw secrets are absent from the database and logs.

### Milestone 2 — Worker, batching, and policy

- Implement the durable event queue and worker loop.
- Implement deterministic routing, urgent bypass, batching, cooldowns, quiet hours, and long-task timers.
- Ensure worker restart recovers pending events.

**Exit criteria:** five near-simultaneous completion events produce one batch; urgent events bypass batching; policy tests cover quiet hours and cooldowns.

### Milestone 3 — Push and safe summarization

- Implement ntfy provider and fake provider.
- Implement template summarizer.
- Add optional NVIDIA NIM and OpenRouter adapters with strict timeout and input budget.
- Keep cloud summarization disabled by default.

**Exit criteria:** fake provider tests pass; a manually triggered live ntfy test works when configured; summarizer failure always falls back to a local template.

### Milestone 4 — Phone alerts

- Implement Twilio REST provider using inline TwiML and XML-safe speech.
- Add strict call feature flag, destination allow-list, time limit, explicit live-test confirmation, and ntfy fallback.
- Document India eligibility and local telecom checks.

**Exit criteria:** fake-provider tests cover success, timeout, malformed response, and fallback. Real calling remains opt-in and is not required for the automated test suite.

### Milestone 5 — Agent adapters and Windows setup

- Implement Claude Code hook adapter and generated hook snippet.
- Implement Codex `notify` argument adapter and generated user-level config snippet.
- Implement OpenCode plugin bridge with documented event mappings.
- Implement generic PowerShell-compatible process wrapper for Hermes/KiloCode/other CLIs.
- Add scripts for starting the worker and optionally registering a current-user startup task.

**Exit criteria:** adapter fixtures pass; setup docs explain which event types each tool can and cannot report; no integration silently rewrites global configuration.

### Milestone 6 — Hardening and release

- Add `jesko doctor`, simulation commands, structured logs, retention cleanup, and final docs.
- Run the full test suite and type/lint checks.
- Audit for secret leakage, shell injection, path leakage, and accidental live network calls in tests.

**Exit criteria:** all acceptance criteria below pass and the README gives a reproducible Windows setup path.

---

## 14. Acceptance test checklist

### Core behavior

- [ ] Valid Claude Code fixture becomes a canonical `task.completed` event.
- [ ] Valid Codex `agent-turn-complete` payload becomes a canonical completion event.
- [ ] Valid OpenCode `session.idle` becomes a canonical completion event.
- [ ] OpenCode `session.error` becomes a failure event.
- [ ] OpenCode `permission.asked` becomes a permission-needed event.
- [ ] Generic wrapper emits start and end events and preserves child exit code.
- [ ] Malformed JSON is rejected without a crash.

### Privacy and security

- [ ] API-key patterns, bearer tokens, JWTs, passwords, and private-key blocks are redacted.
- [ ] Full project paths are never sent to ntfy or Twilio.
- [ ] Raw prompt and full transcript are not stored or transmitted.
- [ ] Cloud summarization is disabled by default.
- [ ] Logs and `doctor` output never reveal credential values or the full ntfy topic.
- [ ] TwiML speech content is XML escaped.
- [ ] The process wrapper does not use `shell=True`.

### Policy and delivery

- [ ] Completion events are batched within configured thresholds.
- [ ] Urgent events bypass batching.
- [ ] Duplicate events are suppressed.
- [ ] Quiet hours suppress voice calls but preserve ntfy push by default.
- [ ] Call cooldown prevents repeated calls for the same task/session.
- [ ] Failed phone calls fall back to ntfy.
- [ ] Summarizer timeout/provider failure falls back to the template.
- [ ] Worker restarts recover queued work.

### Non-interference

- [ ] Every hook/adapter returns control without making an agent permission decision.
- [ ] Notification provider failure does not change the source agent's exit status.
- [ ] No remote endpoint can trigger a command or agent action.
- [ ] Automated tests use fake providers only.

---

## 15. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agent event APIs differ or change | Missing alerts or broken adapters | Version-aware adapters, fixtures, capability matrix, graceful ignore of unknown events. |
| Codex exposes only completion through `notify` | No native error/permission call alerts | State the limitation; offer optional process wrapper for process-level exit status. |
| Twilio calling to India is restricted | Phone alert may not reach a +91 destination | Keep disabled by default; verify Twilio's current regional rules and account eligibility; make provider replaceable. |
| ntfy topic leaks | Unwanted parties may read or publish messages | High-entropy topic, never log it, optionally use authentication or a self-hosted server. |
| LLM summary includes sensitive details | Data leakage | Cloud opt-in, redact before and after LLM, hard input/output limits, template fallback. |
| Hooks delay or interfere with agent | Developer workflow disrupted | Queue locally, short timeout, asynchronous handling, fail-open semantics, no decisions. |
| Multiple agents finish together | Excessive calls/notifications | Short completion batching, deduplication, per-agent/session cooldowns. |

---

## 16. Windows-first setup expectations

The first implementation should target a normal Windows 10/11 developer environment:

- Python 3.11 or later.
- `pipx` or a virtual environment for installation.
- PowerShell scripts for starting the JESKO worker and optional current-user startup registration.
- User data under `%LOCALAPPDATA%\JESKO` or a platform-appropriate application data directory.
- User configuration under `%APPDATA%\JESKO`.
- No Docker, containers, public server, Cloudflare Tunnel, or administrator privileges required for basic operation.

The worker should run in the foreground by default. Startup-task registration must be opt-in and must only affect the current Windows user.

---

## 17. Stage 2 — Deliberately deferred

Stage 2 may add a two-way conversational phone agent. The earlier proposal considered Twilio + Pipecat + FastAPI/WebSocket, NVIDIA speech services, and controlled read-only tools. None of that belongs in the Stage 1 code path.

Before Stage 2, separately design:

- Authentication for incoming call sessions.
- Spoken confirmation and a strong second factor for sensitive actions.
- Strict read-only tools first.
- Project allow-listing and path validation.
- No arbitrary shell execution.
- Tool-level audit logs and call/session retention.
- Human approval for any action that starts or changes an agent task.
- India-specific telephony provider and regulatory review.

Stage 1's architecture should leave room for a later conversational interface, but it must not include a dormant remote-control endpoint.

---

## 18. Decisions to retain for the first build

1. Product name is **JESKO**. Its full form is intentionally pending the creator's definition.
2. Build Stage 1 only.
3. Windows-first, local-first, Python 3.11+.
4. SQLite queue; no public server.
5. ntfy is the required first notification channel.
6. Twilio provider is implemented but disabled by default; India calling eligibility is a deployment gate.
7. Cloud summarization is opt-in; local template is always available.
8. Claude Code, Codex, and OpenCode adapters must reflect their actual event coverage.
9. Hermes/KiloCode use the generic process wrapper unless a stable native event contract is independently verified.
10. JESKO never approves, denies, starts, or controls an agent in Stage 1.

---

## 19. Reference documentation

The following official documentation was checked while preparing this draft. Verify it again when implementing because third-party APIs and regional restrictions can change.

- Claude Code hooks reference: <https://code.claude.com/docs/en/hooks>
- Codex advanced configuration (`notify`): <https://developers.openai.com/codex/config-advanced>
- Codex configuration reference: <https://developers.openai.com/codex/config-reference>
- OpenCode plugins and events: <https://dev.opencode.ai/docs/plugins/>
- ntfy publishing and topic security: <https://docs.ntfy.sh/publish/>
- Twilio Calls API: <https://www.twilio.com/docs/voice/api/call-resource>
- Twilio India Voice Guidelines: <https://www.twilio.com/en-us/guidelines/in/voice>
- TRAI explanation of unsolicited commercial communication: <https://www.trai.gov.in/what-spam-or-ucc>
- NVIDIA NIM developer access FAQ: <https://docs.api.nvidia.com/nim/docs/product>

---

**Document owner:** JESKO creator  
**Open item:** Creator to provide the official expansion of “JESKO”.
