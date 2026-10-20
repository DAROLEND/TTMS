from __future__ import annotations

import uuid
from datetime import datetime

from task_manager.domain.enums import Status
from task_manager.domain.notifiable import Notifiable
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember


class Project(Notifiable):
    def __init__(self, name: str, *, deadline: datetime | None = None, id: str | None = None) -> None:
        self._id = id or str(uuid.uuid4())
        self._name = name
        self._deadline = deadline
        self._tasks: dict[str, Task] = {}
        self._members: dict[str, TeamMember] = {}

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        raise NotImplementedError

    @property
    def deadline(self) -> datetime | None:
        return self._deadline

    @property
    def tasks(self) -> tuple[Task, ...]:
        return tuple(self._tasks.values())

    @property
    def members(self) -> tuple[TeamMember, ...]:
        return tuple(self._members.values())

    def add_task(self, task: Task) -> None:
        """Raises: ValidationError (дубль id), MemberNotFoundError (виконавець не з проєкту)"""
        raise NotImplementedError

    def add_member(self, member: TeamMember) -> None:
        """Raises: ValidationError (дубль id)"""
        raise NotImplementedError

    def get_task(self, task_id: str) -> Task:
        """Raises: TaskNotFoundError"""
        raise NotImplementedError

    def get_member(self, member_id: str) -> TeamMember:
        """Raises: MemberNotFoundError"""
        raise NotImplementedError

    def assign_task(self, task_id: str, member_id: str) -> None:
        """Raises: TaskNotFoundError, MemberNotFoundError"""
        raise NotImplementedError

    def unassign_task(self, task_id: str) -> None:
        """Raises: TaskNotFoundError"""
        raise NotImplementedError

    def get_tasks_by_status(self, status: Status) -> list[Task]:
        raise NotImplementedError

    def completion_rate(self) -> float:
        """DONE / (усі - CANCELLED), від 0.0 до 1.0."""
        raise NotImplementedError

    def set_deadline(self, deadline: datetime | None, *, now: datetime | None = None) -> None:
        """Raises: DeadlineInPastError"""
        raise NotImplementedError

    def days_until_deadline(self, now: datetime | None = None) -> int | None:
        """0 - сьогодні, < 0 - минув, None - не встановлено."""
        raise NotImplementedError

    def get_notification_message(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"Project(id={self._id!r}, name={self._name!r}, "
            f"tasks={len(self._tasks)}, members={len(self._members)})"
        )
