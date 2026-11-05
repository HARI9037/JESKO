from .adapters import claude, codex, opencode
from .storage import Storage
def ingest(storage, adapter, payload):
    event = {"claude":claude,"codex":codex,"opencode":opencode}[adapter](payload); return storage.add(event)
