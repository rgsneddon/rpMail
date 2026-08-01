"""Calendar pillar — events create + serialize (from-scratch Outlook variant)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CalendarEvent:
    title: str
    start_unix: int
    end_unix: int
    location: str = ""
    notes: str = ""
    recurrence: str = ""  # optional RRULE-like string; partial support
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalendarEvent":
        return cls(
            title=str(data.get("title") or "Event"),
            start_unix=int(data.get("start_unix") or 0),
            end_unix=int(data.get("end_unix") or 0),
            location=str(data.get("location") or ""),
            notes=str(data.get("notes") or ""),
            recurrence=str(data.get("recurrence") or ""),
            event_id=str(data.get("event_id") or uuid.uuid4().hex[:12]),
        )


@dataclass
class CalendarStore:
    events: list[CalendarEvent] = field(default_factory=list)

    def add_event(
        self,
        title: str,
        start_unix: int | None = None,
        end_unix: int | None = None,
        **kwargs: Any,
    ) -> CalendarEvent:
        now = int(time.time())
        start = int(start_unix if start_unix is not None else now)
        end = int(end_unix if end_unix is not None else start + 3600)
        if end < start:
            raise ValueError("end_unix must be >= start_unix")
        ev = CalendarEvent(title=title, start_unix=start, end_unix=end, **kwargs)
        self.events.append(ev)
        return ev

    def list_events(self) -> list[CalendarEvent]:
        return sorted(self.events, key=lambda e: e.start_unix)

    def dumps(self) -> str:
        return json.dumps(
            {"events": [e.to_dict() for e in self.events]},
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def loads(cls, raw: str) -> "CalendarStore":
        data = json.loads(raw)
        store = cls()
        for e in data.get("events") or []:
            store.events.append(CalendarEvent.from_dict(e))
        return store
