"""Ajan çalışma logları — in-memory ring buffer.
Frontend polling ile canlı log gösterir.
"""
import time
from collections import defaultdict, deque
from typing import Optional

# {run_id: [{"step": str, "msg": str, "ts": float}, ...]}
_runs: dict[str, list[dict]] = defaultdict(list)
# aktif çalışan run'lar
_active: dict[str, str] = {}  # {run_id: "running"|"error"}
LOCK = __import__("threading").Lock()


def start_run(slug: str) -> str:
    run_id = f"{slug}_{int(time.time() * 1000)}"
    with LOCK:
        _active[run_id] = "running"
    log_step(run_id, "start", f"Ajan başlatıldı: {slug}")
    return run_id


def log_step(run_id: str, step: str, msg: str):
    with LOCK:
        _runs[run_id].append({"step": step, "msg": msg, "ts": time.time()})


def end_run(run_id: str, error: Optional[str] = None):
    with LOCK:
        _active[run_id] = "error" if error else "done"


def get_run_logs(run_id: str) -> dict:
    with LOCK:
        logs = _runs.get(run_id, [])
        status = _active.get(run_id, "unknown")
    return {"run_id": run_id, "status": status, "steps": logs}


def get_active_runs(slug: Optional[str] = None) -> list[dict]:
    with LOCK:
        active = [
            {"run_id": rid, "status": st, "step_count": len(_runs.get(rid, []))}
            for rid, st in _active.items()
            if st == "running" and (slug is None or rid.startswith(slug))
        ]
    return active
