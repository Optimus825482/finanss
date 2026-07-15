"""
ScannerAgent — Stage 1 ilerleme göstergesi.
Tarama mantığı screener_service'tedir. Bu sadece status_banner gibi çalışır.
"""
from app.agents.base import BaseAgent, AgentStatus


class ScannerAgent(BaseAgent):
    name = "scanner"
    label = "Tarama"
