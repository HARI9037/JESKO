from __future__ import annotations
import json, threading
from datetime import datetime
from .batching import CompletionBatcher
from .policy import decide, in_quiet_hours
from .providers import Ntfy, Twilio, ProviderError
from .summarizers import SummaryChain, JsonSummaryProvider

class Worker:
    def __init__(self, storage, config, push=None, call=None):
        self.storage,self.config,self.push,self.call=storage,config,push,call
        providers=[]
        if config.cloud_enabled:
            providers=[JsonSummaryProvider(config.nvidia_base_url,config.nvidia_model,config.nvidia_api_key),JsonSummaryProvider("https://openrouter.ai/api/v1/chat/completions",config.openrouter_model,config.openrouter_api_key)]
        self.summary=SummaryChain(providers,4); self.batch=CompletionBatcher(config.debounce_seconds,config.max_wait_seconds); self.stop_event=threading.Event()
    def _quiet(self): return self.config.quiet_enabled and in_quiet_hours(datetime.now(),self.config.quiet_start,self.config.quiet_end)
    def _push(self, text):
        if not self.config.ntfy_enabled or not self.config.ntfy_topic: raise ProviderError("ntfy unavailable")
        (self.push or Ntfy(self.config.ntfy_server,self.config.ntfy_topic,self.config.ntfy_token)).send(text[:500]); return True
    def _call(self, text):
        if not self.config.calls_enabled or self._quiet(): return False
        (self.call or Twilio(True,self.config.twilio_sid,self.config.twilio_token,self.config.twilio_from,self.config.to_number)).send(text); return True
    def inspect_once(self, limit=50):
        rows=self.storage.pending(limit)
        return [{"id": r["id"], "event_type": json.loads(r["payload"])["event_type"], "status": r["status"], "would_batch": json.loads(r["payload"])["event_type"] == "task.completed"} for r in rows]
    def _flush_batch(self, force=False):
        if not self.batch._events or (not force and not self.batch.ready()): return 0
        events=self.batch.flush(); message=f"{len(events)} agent task completions." if len(events)>1 else self.summary.summarize(events[0])
        try:
            self._push(message)
        except Exception:
            for event in events: self.storage.mark(event["_row_id"],"failed",1,2,event["_claim_token"])
            return 0
        for event in events: self.storage.mark(event["_row_id"],"sent",1,claim_token=event["_claim_token"])
        return len(events)
    def process_once(self, limit=50, force_flush=False):
        handled=0
        for row in self.storage.claim(limit):
            attempts=row["attempts"]+1; event=json.loads(row["payload"]); kind=event["event_type"]
            try:
                decision=decide(kind,self.config.calls_enabled,self._quiet())
                if kind=="task.completed": event["_row_id"]=row["id"]; event["_claim_token"]=row["claim_token"]; self.batch.add(event); continue
                if not decision.push and not decision.call: self.storage.mark(row["id"],"sent",attempts,claim_token=row["claim_token"]); handled+=1; continue
                message=self.summary.summarize(event); delivered=False; push_ok=False; call_ok=False
                if decision.push:
                    try: push_ok=self._push(message); delivered=push_ok
                    except Exception: push_ok=False
                if decision.call:
                    key=f"{event.get('source')}:{event.get('session_id') or event.get('event_id')}"
                    if self.storage.cooldown_ready(key):
                        try: call_ok=self._call(message); delivered=call_ok or delivered
                        except ProviderError: pass
                        if call_ok: self.storage.set_cooldown(key,self.config.urgent_cooldown_minutes*60)
                if not delivered: raise ProviderError("no notification destination")
                self.storage.mark(row["id"],"sent",attempts,claim_token=row["claim_token"]); handled+=1
            except Exception:
                maximum=getattr(self.config,"max_retry_attempts",5); status="failed" if attempts < maximum else "dead_letter"
                self.storage.mark(row["id"],status,attempts,min(300,2**attempts),row["claim_token"])
        self._flush_batch(force_flush)
        return handled
    def run_forever(self, interval=1):
        try:
            while not self.stop_event.is_set(): self.process_once(); self.stop_event.wait(interval)
        finally:
            self._flush_batch(True)

def run_once(storage, config): return Worker(storage, config).process_once()
