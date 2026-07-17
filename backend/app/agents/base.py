"""
BaseAgent: her ajanın uyduğu ortak sözleşme.
Durum (status) burada tutulur ki orchestrator ve API aynı kaynaktan okusun.
"""
from datetime import datetime
from app.config import now_istanbul
from enum import Enum
from typing import Optional


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class BaseAgent:
    name: str = "base"
    label: str = "Base Agent"

    def __init__(self):
        self.status: AgentStatus = AgentStatus.IDLE
        self.detail: Optional[str] = None
        self.updated_at: Optional[datetime] = None

    def _set(self, status: AgentStatus, detail: Optional[str] = None):
        self.status = status
        self.detail = detail
        self.updated_at = now_istanbul()

    def as_dict(self):
        return {
            "name": self.name,
            "label": self.label,
            "status": self.status.value,
            "detail": self.detail,
            "updated_at": self.updated_at,
        }

    async def run(self, *args, **kwargs):
        raise NotImplementedError
