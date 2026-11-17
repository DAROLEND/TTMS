from __future__ import annotations

import uuid
from datetime import datetime

from task_manager.domain.enums import Status
from task_manager.domain.notifiable import Notifiable
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember
from task_manager.exceptions import (
    DeadlineInPastError,
    MemberNotFoundError,
    TaskNotFoundError,
    ValidationError,
)


class Project(Notifiable):
    def __init__(self, name: str, *, deadline: datetime | None = None, id: str | None = None) -> None:
        self._id = id or str(uuid.uuid4())
        self.name = name
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
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("name", "назва проєкту не може бути порожньою")
        self._name = value.strip()

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
        if not isinstance(task, Task):
            raise ValidationError("task", f"очікується Task, отримано {task!r}")
        if task.id in self._tasks:
            raise ValidationError("task", f"завдання з id '{task.id}' уже є в проєкті")
        if task.assignee is not None and task.assignee.id not in self._members:
            raise MemberNotFoundError(task.assignee.id, self._name)
        self._tasks[task.id] = task

    def add_member(self, member: TeamMember) -> None:
        """Raises: ValidationError (дубль id)"""
        if not isinstance(member, TeamMember):
            raise ValidationError("member", f"очікується TeamMember, отримано {member!r}")
        if member.id in self._members:
            raise ValidationError("member", f"учасник з id '{member.id}' уже є в проєкті")
        self._members[member.id] = member

    def get_task(self, task_id: str) -> Task:
        """Raises: TaskNotFoundError"""
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id, self._name)
        return task

    def get_member(self, member_id: str) -> TeamMember:
        """Raises: MemberNotFoundError"""
        member = self._members.get(member_id)
        if member is None:
            raise MemberNotFoundError(member_id, self._name)
        return member

    def assign_task(self, task_id: str, member_id: str) -> None:
        """Raises: TaskNotFoundError, MemberNotFoundError"""
        task = self.get_task(task_id)
        member = self.get_member(member_id)
        task.assign_to(member)

    def unassign_task(self, task_id: str) -> None:
        """Raises: TaskNotFoundError"""
        self.get_task(task_id).assign_to(None)

    def get_tasks_by_status(self, status: Status) -> list[Task]:
        return [task for task in self._tasks.values() if task.status is status]

    def completion_rate(self) -> float:
        """DONE / (усі - CANCELLED), від 0.0 до 1.0."""
        relevant = [task for task in self._tasks.values() if task.status is not Status.CANCELLED]
        if not relevant:
            return 0.0
        done = sum(1 for task in relevant if task.status is Status.DONE)
        return done / len(relevant)

    def set_deadline(self, deadline: datetime | None, *, now: datetime | None = None) -> None:
        """Raises: DeadlineInPastError"""
        if deadline is not None and deadline < (now or datetime.now()):
            raise DeadlineInPastError(deadline, self._name)
        self._deadline = deadline

    def days_until_deadline(self, now: datetime | None = None) -> int | None:
        """0 - сьогодні, < 0 - минув, None - не встановлено."""
        if self._deadline is None:
            return None
        today = (now or datetime.now()).date()
        return (self._deadline.date() - today).days

    def get_notification_message(self) -> str:
        progress = f"виконано {self.completion_rate():.0%}"
        days = self.days_until_deadline()
        if days is None:
            return f"Проєкт '{self._name}': дедлайн не встановлено, {progress}"
        if days > 0:
            return f"Проєкт '{self._name}': до дедлайну {days} дн., {progress}"
        if days == 0:
            return f"Проєкт '{self._name}': дедлайн сьогодні, {progress}"
        return f"Проєкт '{self._name}': дедлайн минув {-days} дн. тому, {progress}"

    def __repr__(self) -> str:
        return (
            f"Project(id={self._id!r}, name={self._name!r}, "
            f"tasks={len(self._tasks)}, members={len(self._members)})"
        )
