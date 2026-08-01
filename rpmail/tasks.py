"""Tasks pillar — create + complete + persist."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Task:
    title: str
    body: str = ""
    priority: int = 0  # 0=normal, higher = more urgent
    completed: bool = False
    completed_unix: int | None = None
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_unix: int = field(default_factory=lambda: int(time.time()))

    def complete(self) -> None:
        self.completed = True
        self.completed_unix = int(time.time())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            title=str(data.get("title") or ""),
            body=str(data.get("body") or ""),
            priority=int(data.get("priority") or 0),
            completed=bool(data.get("completed")),
            completed_unix=data.get("completed_unix"),
            task_id=str(data.get("task_id") or uuid.uuid4().hex[:12]),
            created_unix=int(data.get("created_unix") or 0),
        )


@dataclass
class TaskList:
    tasks: list[Task] = field(default_factory=list)

    def add(self, title: str, **kwargs: Any) -> Task:
        t = Task(title=title, **kwargs)
        self.tasks.append(t)
        return t

    def complete(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.task_id == task_id:
                t.complete()
                return t
        raise KeyError(f"task not found: {task_id}")

    def open_tasks(self) -> list[Task]:
        return [t for t in self.tasks if not t.completed]

    def dumps(self) -> str:
        return json.dumps(
            {"tasks": [t.to_dict() for t in self.tasks]},
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def loads(cls, raw: str) -> "TaskList":
        data = json.loads(raw)
        tl = cls()
        for t in data.get("tasks") or []:
            tl.tasks.append(Task.from_dict(t))
        return tl
