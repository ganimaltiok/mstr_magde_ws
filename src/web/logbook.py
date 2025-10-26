from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock
from typing import Deque, List, Optional


@dataclass
class RequestLogEntry:
    timestamp: datetime
    method: str
    url: str
    status: int
    duration_ms: int
    remote_addr: str
    response_size: int
    response_json: Optional[str] = None


_MAX_ENTRIES = 250
_entries: Deque[RequestLogEntry] = deque(maxlen=_MAX_ENTRIES)
_lock = Lock()


def add_entry(entry: RequestLogEntry) -> None:
    with _lock:
        _entries.appendleft(entry)


def list_entries() -> List[RequestLogEntry]:
    with _lock:
        return list(_entries)


def to_serialisable(entry: RequestLogEntry) -> dict:
    data = asdict(entry)
    data["timestamp"] = entry.timestamp.isoformat(timespec="seconds")
    return data


__all__ = ["RequestLogEntry", "add_entry", "list_entries", "to_serialisable"]

