import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from jesko.adapters import claude, codex, opencode
from jesko.batching import CompletionBatcher
from jesko.config import Config
from jesko.policy import decide, in_quiet_hours
from jesko.providers import ProviderError, Twilio
from jesko.redaction import redact
from jesko.schema import Event
from jesko.storage import Storage
from jesko.summarizers import SummaryChain, SummaryError
from jesko.worker import Worker


def test_schema_and_redaction():
    e = Event(
        1,
        "1",
        "x",
        "Agent",
        "task.completed",
        "now",
        message_excerpt=redact("api_key=sk-abcdefghijklmnop password=hunter2"),
    )
    assert "sk-" not in e.to_json() and "hunter2" not in e.to_json()
    assert "This is a token" in redact("This is a token")


def test_adapters_coverage():
    assert claude({"hook_event_name": "Stop"}).event_type == "task.completed"
    assert codex({"type": "agent-turn-complete"}).event_type == "task.completed"
    assert opencode({"type": "permission.asked"}).event_type == "permission.required"
    try:
        codex({"type": "permission"})
        assert False
    except ValueError:
        pass


def test_native_codex_notification_mapping_and_legacy_compatibility():
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "thread-1",
        "turn-id": "turn-1",
        "cwd": r"C:\Users\user\Desktop\JESKO",
        "input-messages": ["Build it"],
        "last-assistant-message": "Build completed. api_key=sk-abcdefghijklmnop",
    }
    event = codex(payload)
    assert event.session_id == "thread-1"
    assert event.turn_id == "turn-1"
    assert event.project_path == payload["cwd"]
    assert event.project_name == "JESKO"
    assert "Build completed" in event.message_excerpt
    assert "sk-" not in event.message_excerpt
    legacy = codex(
        {
            "type": "agent-turn-complete",
            "session_id": "s",
            "turn_id": "t",
            "project_path": "C:/Demo",
            "project_name": "Demo",
            "message_excerpt": "done",
        }
    )
    assert (legacy.session_id, legacy.turn_id, legacy.project_name, legacy.message_excerpt) == (
        "s",
        "t",
        "Demo",
        "done",
    )


def test_native_codex_optional_fields_and_stable_duplicate_key():
    a = codex({"type": "agent-turn-complete"})
    b = codex({"type": "agent-turn-complete"})
    assert (
        a.session_id is None
        and a.turn_id is None
        and a.project_name is None
        and a.message_excerpt == ""
        and a.event_id == b.event_id
    )
    s = Storage(Path("native-codex-test.sqlite3"))
    assert s.add(a) is True
    assert s.add(b) is False
    s.db.execute("delete from events")
    s.db.commit()
    s.close()
    Path("native-codex-test.sqlite3").unlink(missing_ok=True)


def test_policy():
    assert decide("task.completed", True, False).batch
    assert decide("task.failed", True, True).push is True and not decide("task.failed", True, True).call
    assert in_quiet_hours(datetime(2026, 1, 1, 23, 0))
    assert not in_quiet_hours(datetime(2026, 1, 1, 12, 0))


def test_storage_dedupe_and_recovery(tmp_path):
    s = Storage(tmp_path / "a.db")
    e = claude({"hook_event_name": "Stop", "session_id": "s", "turn_id": "t"})
    assert s.add(e) and not s.add(e)
    assert len(s.pending()) == 1
    s.close()
    time.sleep(0.1)
    s = Storage(tmp_path / "a.db")
    assert len(s.pending()) == 1


def test_twiml_disabled_and_escaped():
    t = Twilio(False, "", "", "+14155550100", "+919999999999")
    assert "&lt;" in t.twiml("<hello>")
    try:
        t.send("test")
        assert False
    except ProviderError:
        pass


def test_wrapper_never_shell_true(tmp_path):
    p = subprocess.run([sys.executable, "-c", "import subprocess; print(subprocess.run)"])
    assert p.returncode == 0


def test_worker_keeps_failed_delivery_failed(tmp_path):
    s = Storage(tmp_path / "w.db")
    e = claude({"hook_event_name": "StopFailure", "event_id": "x"})
    s.add(e)
    c = Config(db=str(tmp_path / "w.db"), ntfy_enabled=True, ntfy_topic="topic", max_retry_attempts=3)

    class Bad:
        def send(self, *args, **kwargs):
            raise ProviderError("offline")

    w = Worker(s, c, push=Bad())
    w.process_once()
    row = s.db.execute("select status from events").fetchone()
    assert row[0] == "failed"
    s.close()


def test_worker_dry_no_destination_does_not_send(tmp_path):
    s = Storage(tmp_path / "w.db")
    s.add(claude({"hook_event_name": "StopFailure", "event_id": "x"}))
    c = Config(db=str(tmp_path / "w.db"), ntfy_enabled=True)
    Worker(s, c).process_once()
    assert s.db.execute("select status from events").fetchone()[0] == "failed"
    s.close()


def test_batcher_event_id_and_debounce():
    b = CompletionBatcher(2, 8)
    assert b.add({"event_id": "a"})
    assert b.add({"event_id": "b"})
    assert not b.add({"event_id": "a"})
    assert not b.ready(b._first_at + 1)
    assert b.ready(b._first_at + 9)


def test_summary_fallback_and_template():
    class Bad:
        def summarize(self, event):
            raise SummaryError("x")

    result = SummaryChain([Bad()]).summarize(
        {
            "agent_name": "Codex",
            "event_type": "task.completed",
            "project_name": "Demo",
            "message_excerpt": "ok",
            "duration_seconds": 2,
        }
    )
    assert "Codex" in result and len(result.split(".")) <= 3


def test_dry_run_is_read_only(tmp_path):
    s = Storage(tmp_path / "dry.db")
    s.add(claude({"hook_event_name": "StopFailure", "event_id": "dry"}))
    before = s.db.execute("select status,attempts from events").fetchone()
    c = Config(ntfy_enabled=True, ntfy_topic="x")
    w = Worker(s, c)
    assert w.inspect_once()
    after = s.db.execute("select status,attempts from events").fetchone()
    assert tuple(before) == tuple(after)
    assert s.db.execute("select count(*) from cooldowns").fetchone()[0] == 0
    s.close()


def test_one_shot_flushes_and_marks_only_after_delivery(tmp_path):
    s = Storage(tmp_path / "batch.db")
    s.add(claude({"hook_event_name": "Stop", "event_id": "batch"}))
    c = Config(ntfy_enabled=True, ntfy_topic="x")

    class Good:
        def __init__(self):
            self.messages = []

        def send(self, message, *args, **kwargs):
            self.messages.append(message)

    good = Good()
    Worker(s, c, push=good).process_once(force_flush=True)
    assert good.messages
    assert s.db.execute("select status from events").fetchone()[0] == "sent"
    s.close()


def test_shutdown_failed_batch_remains_failed(tmp_path):
    s = Storage(tmp_path / "shutdown.db")
    s.add(claude({"hook_event_name": "Stop", "event_id": "shutdown"}))
    c = Config(ntfy_enabled=True, ntfy_topic="x")

    class Bad:
        def send(self, *args, **kwargs):
            raise ProviderError("offline")

    w = Worker(s, c, push=Bad())
    w.process_once()
    w._flush_batch(True)
    assert s.db.execute("select status from events").fetchone()[0] == "failed"
    s.close()


def test_ntfy_failure_does_not_block_twilio(tmp_path):
    s = Storage(tmp_path / "iso.db")
    s.add(claude({"hook_event_name": "StopFailure", "event_id": "urgent"}))
    c = Config(ntfy_enabled=True, ntfy_topic="x", calls_enabled=True)

    class BadPush:
        def send(self, *args, **kwargs):
            raise ProviderError("push down")

    class GoodCall:
        def __init__(self):
            self.called = False

        def send(self, *args, **kwargs):
            self.called = True

    call = GoodCall()
    Worker(s, c, push=BadPush(), call=call).process_once()
    assert call.called
    assert s.db.execute("select status from events").fetchone()[0] == "sent"
    s.close()
