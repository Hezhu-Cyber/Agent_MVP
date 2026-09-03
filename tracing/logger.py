from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class TraceLogger:
    def __init__(self, path: str | Path = "logs/traces.jsonl", *, console: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.console = console
        self._lock = Lock()
        self._logger = logging.getLogger("mini_agent.trace")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

    @staticmethod
    def _safe(value: Any, limit: int = 1000) -> Any:
        if isinstance(value, str):
            return value if len(value) <= limit else value[:limit] + "...<truncated>"
        if isinstance(value, dict):
            return {key: TraceLogger._safe(item, limit) for key, item in value.items()}
        if isinstance(value, list):
            return [TraceLogger._safe(item, limit) for item in value]
        return value

    def event(self, event_type: str, **payload: Any) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **self._safe(payload),
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if self.console:
            trace_id = payload.get("trace_id", "-")
            step = payload.get("step", "-")
            summary = payload.get("decision_type") or payload.get("tool_name") or ""
            self._logger.info(
                "[trace=%s][step=%s] %s %s", trace_id, step, event_type, summary
            )
