# JESKO

JESKO is a Windows-first, local-first, one-way notification companion for AI coding agents. The acronym expansion is intentionally unspecified. Stage 1 stores sanitized lifecycle events in SQLite, routes completion/urgent alerts, publishes ntfy notifications, and optionally places short Twilio calls. Calls and cloud summarization are disabled by default.

Install with `py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e .; pip install -r requirements-dev.txt`. Run `jesko init`, then `jesko ingest --adapter codex --stdin`, `jesko codex-notify '{"type":"agent-turn-complete"}'`, `jesko simulate fixture.json`, or `jesko run --agent KiloCode -- kilo`. Run tests with `py -m pytest`.

Configuration environment variables: `JESKO_CLOUD_SUMMARIZATION_ENABLED`, `JESKO_NVIDIA_API_KEY`, `JESKO_NVIDIA_BASE_URL`, `JESKO_NVIDIA_MODEL`, `JESKO_OPENROUTER_API_KEY`, `JESKO_OPENROUTER_MODEL`, `JESKO_NTFY_TOPIC`, `JESKO_NTFY_TOKEN`, `JESKO_CALLS_ENABLED`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `JESKO_TO_NUMBER`, and optional `JESKO_TWILIO_REGION`.

Use `jesko worker --once` for one processing cycle or `jesko worker --dry-run` to inspect without delivery. Failed deliveries remain `failed` until the configured retry limit, then become `dead_letter`; they are never marked `sent` without successful delivery. `jesko test-call` is a dry run unless `--confirm` is supplied, and Twilio remains disabled by default.

`worker --dry-run` only reads eligible events and does not claim, retry, update status, or create cooldowns. `worker --once` force-flushes completion batches so claimed rows are either marked `sent` after delivery or retained as failed for retry. During shutdown, pending batch rows are summarized and updated individually.

No raw payloads, prompts, code, secrets, full paths, remote execution, permission decisions, public server, or telemetry are part of Stage 1. Provider tests are fake/mocked and do not access live endpoints. Twilio India availability is not assumed; verify account, caller ID, destination eligibility, and applicable telecom obligations before any explicit test call.
