# Security and privacy

Events are validated, redacted, bounded, and stored locally. API keys, bearer tokens, JWT-like values, password assignments, cloud keys, and PEM private keys are redacted. Project paths remain local and are not notification text. ntfy topics are secret-like high-entropy capabilities and are never logged. Cloud summarization requires explicit opt-in and only receives a short redacted excerpt; local templates are the default. Twilio is disabled by default and fixed to the configured E.164 destination.

SQLite uses WAL mode and transactional claims so concurrent workers do not process the same row. Processing leases are recoverable after restart. Delivery failures use bounded exponential backoff and eventually enter `dead_letter`; retention cleanup only removes old `sent` rows.

Worker dry-run mode reads eligible events without claiming, incrementing attempts, changing status, or creating cooldowns. Twilio escalation is attempted independently of ntfy outcome and remains disabled unless explicitly enabled.

Completion batches retain their SQLite claim tokens until delivery succeeds. A failed batch is returned to retryable state; no generic shutdown message is treated as delivery for the individual events.
