"""Optional outbound webhook (Slack-ish). Never raises."""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def notify_webhook(title: str, body: str, extra: dict | None = None) -> bool:
    """POST to WEBHOOK_URL env if set (Slack-ish json {text: ...}). Never raise."""
    url = os.getenv("WEBHOOK_URL", "").strip()
    if not url:
        return False
    text = f"*{title}*\n{body}" if title else body
    payload: dict = {"text": text}
    if extra:
        payload["extra"] = extra
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except Exception as e:
        logger.warning("webhook notify failed: %s", e)
        return False
