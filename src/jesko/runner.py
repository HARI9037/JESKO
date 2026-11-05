from __future__ import annotations
import subprocess, time
from .schema import Event, now_iso, stable_id
def run(agent: str, command: list[str], ingest):
    start=time.monotonic(); base={"event_id":stable_id([agent, command, start]), "occurred_at":now_iso()}; ingest(Event(1,base["event_id"],"wrapper",agent,"task.started",base["occurred_at"]))
    result=subprocess.run(command, shell=False); kind="task.completed" if result.returncode == 0 else "task.failed"; ingest(Event(1,stable_id([base["event_id"],result.returncode]),"wrapper",agent,kind,now_iso(),duration_seconds=time.monotonic()-start)); return result.returncode
