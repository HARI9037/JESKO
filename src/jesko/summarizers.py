from __future__ import annotations
import json, time
from urllib import request
from .redaction import redact

class SummaryError(Exception): pass

def template(event: dict) -> str:
    agent = redact(str(event.get("agent_name") or "agent"), 80)
    project = redact(str(event.get("project_name") or "the project"), 80)
    kind = str(event.get("event_type", "agent.notice")).replace(".", " ")
    return redact(f"{agent} {kind} in {project}.", 240)

class JsonSummaryProvider:
    def __init__(self, endpoint: str, model: str, api_key: str, timeout: float = 1.5):
        self.endpoint, self.model, self.api_key, self.timeout = endpoint, model, api_key, timeout
    def summarize(self, event: dict) -> str:
        if not self.endpoint or not self.model or not self.api_key: raise SummaryError("provider not configured")
        safe = {k: event.get(k) for k in ("agent_name", "event_type", "project_name", "message_excerpt", "duration_seconds")}
        safe["message_excerpt"] = redact(str(safe.get("message_excerpt") or ""), 1000)
        body = json.dumps({"model": self.model, "messages": [{"role":"user", "content": json.dumps(safe)}]}).encode()
        req = request.Request(self.endpoint, data=body, method="POST", headers={"Content-Type":"application/json", "Authorization":"Bearer " + self.api_key})
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read())
            text = data["choices"][0]["message"]["content"]
            return redact(" ".join(str(text).split())[:500], 500)
        except Exception as exc: raise SummaryError("summary provider failed") from exc

class SummaryChain:
    def __init__(self, providers=(), budget_seconds: float = 4): self.providers, self.budget_seconds = tuple(providers), budget_seconds
    def summarize(self, event: dict) -> str:
        started = time.monotonic()
        for provider in self.providers:
            if time.monotonic() - started >= self.budget_seconds: break
            try: return provider.summarize(event)
            except SummaryError: continue
        return template(event)
