from __future__ import annotations
import argparse, json, sys
from .paths import ensure_dirs, config_dir, db_path
from .config import load_config
from .storage import Storage
from .ingestion import ingest
from .adapters import parse_json
from .providers import Ntfy, Twilio, ProviderError
from .runner import run
from .worker import Worker
def main(argv=None):
    p=argparse.ArgumentParser(prog="jesko"); sub=p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init"); sub.add_parser("doctor"); w=sub.add_parser("worker"); w.add_argument("--once", action="store_true"); w.add_argument("--dry-run", action="store_true"); sub.add_parser("test-push")
    tc=sub.add_parser("test-call"); tc.add_argument("--confirm", action="store_true")
    i=sub.add_parser("ingest"); i.add_argument("--adapter", required=True); i.add_argument("--stdin", action="store_true")
    c=sub.add_parser("codex-notify"); c.add_argument("payload")
    s=sub.add_parser("simulate"); s.add_argument("fixture")
    r=sub.add_parser("run"); r.add_argument("--agent", required=True); r.add_argument("command", nargs=argparse.REMAINDER)
    a=p.parse_args(argv); cfg=load_config()
    if a.cmd=="init": ensure_dirs(); (config_dir()/"jesko.toml").write_text('[app]\nname="JESKO"\n[ntfy]\nenabled=true\nserver="https://ntfy.sh"\n[twilio]\nenabled=false\n[summarization]\nenabled=false\n', encoding="utf-8"); print(config_dir()/"jesko.toml"); return 0
    if a.cmd=="doctor": print(f"config_dir={config_dir()}\ndb={db_path()}\nntfy_topic_configured={bool(cfg.ntfy_topic)}\ncalls_enabled={cfg.calls_enabled}"); return 0
    if a.cmd in {"ingest","codex-notify","simulate"}:
        ensure_dirs(); st=Storage(db_path())
        try:
            if a.cmd=="ingest":
                if not a.stdin: p.error("ingest requires --stdin")
                payload=parse_json(sys.stdin.read()); adapter=a.adapter
            elif a.cmd=="codex-notify": payload=parse_json(a.payload); adapter="codex"
            else: payload=json.loads(open(a.fixture, encoding="utf-8").read()); adapter=payload.pop("adapter", "codex")
            print("queued" if ingest(st,adapter,payload) else "duplicate"); return 0
        except (ValueError, KeyError, json.JSONDecodeError) as e: print("ignored: invalid payload", file=sys.stderr); return 0
    if a.cmd=="test-push":
        if not cfg.ntfy_enabled or not cfg.ntfy_topic:
            print("ntfy not configured: set JESKO_NTFY_TOPIC and ensure ntfy.enabled=true in config")
            return 1
        Ntfy(cfg.ntfy_server,cfg.ntfy_topic,cfg.ntfy_token).send("JESKO test push", "JESKO test"); return 0
    if a.cmd=="test-call":
        provider=Twilio(cfg.calls_enabled, cfg.twilio_sid, cfg.twilio_token, cfg.twilio_from, cfg.to_number)
        print(f"recipient={provider.masked_destination()} calls_enabled={cfg.calls_enabled} region={cfg.twilio_region or 'unspecified'}")
        if not a.confirm: print("dry run; add --confirm to place a call"); return 0
        if not cfg.calls_enabled: print("refusing call: Twilio is disabled"); return 2
        try: provider.send("JESKO test call."); print("call submitted"); return 0
        except ProviderError as exc: print(f"call not submitted: {exc}"); return 2
    if a.cmd=="run":
        ensure_dirs(); st=Storage(db_path()); return run(a.agent, a.command[1:] if a.command and a.command[0]=="--" else a.command, st.add)
    if a.cmd=="worker":
        ensure_dirs(); st=Storage(db_path())
        worker=Worker(st,cfg); print(f"worker once={a.once} dry_run={a.dry_run} ntfy={cfg.ntfy_enabled and bool(cfg.ntfy_topic)} calls={cfg.calls_enabled}")
        if a.dry_run:
            for item in worker.inspect_once(): print(f"id={item['id']} event={item['event_type']} would_batch={item['would_batch']}")
            st.close(); return 0
        if a.once: worker.process_once(force_flush=True); st.close(); return 0
        try: worker.run_forever()
        except KeyboardInterrupt: worker.stop_event.set()
        finally: st.close()
        return 0
    return 0
