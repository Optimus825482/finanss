"""Ajan çalışma logları — in-memory ring buffer.
Frontend polling ile canlı log gösterir.
Agent kendi içinden `log_if_active(slug, step, msg)` ile log basabilir.
"""
import time
from collections import defaultdict, deque
from typing import Optional

_runs: dict[str, list[dict]] = defaultdict(list)
_active: dict[str, str] = {}          # {run_id: "running"|"done"|"error"}
_slug_to_run: dict[str, str] = {}     # {slug: run_id} — agent içinden log basmak için
LOCK = __import__("threading").Lock()


def start_run(slug: str) -> str:
    run_id = f"{slug}_{int(time.time() * 1000)}"
    with LOCK:
        _active[run_id] = "running"
        _slug_to_run[slug] = run_id
    log_step(run_id, "start", f"Ajan başlatıldı: {slug}")
    return run_id


def log_step(run_id: str, step: str, msg: str):
    with LOCK:
        _runs[run_id].append({"step": step, "msg": msg, "ts": time.time()})


def log_if_active(slug: str, step: str, msg: str):
    """Agent içinden log basmak için — hangi run_id aktif bilmeden."""
    with LOCK:
        rid = _slug_to_run.get(slug)
    if rid:
        log_step(rid, step, msg)


def end_run(run_id: str, error: Optional[str] = None):
    status = "error" if error else "done"
    with LOCK:
        _active[run_id] = status
        # Cleanup slug mapping after 5 min
        for s, rid in list(_slug_to_run.items()):
            if rid == run_id:
                del _slug_to_run[s]


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
