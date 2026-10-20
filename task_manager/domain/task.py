from __future__ import annotations

import uuid
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from task_manager.domain.enums import Priority, Status
from task_manager.domain.notifiable import Notifiable

if TYPE_CHECKING:
    from task_manager.domain.team_member import TeamMember


class Task(Notifiable):
    ALLOWED_TRANSITIONS = MappingProxyType({
        Status.TODO: frozenset({Status.IN_PROGRESS, Status.CANCELLED}),
        Status.IN_PROGRESS: frozenset({Status.REVIEW, Status.CANCELLED}),
        Status.REVIEW: frozenset({Status.DONE, Status.IN_PROGRESS, Status.CANCELLED}),
        Status.DONE: frozenset(),
        Status.CANCELLED: frozenset(),
    })

    def __init__(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        deadline: datetime | None = None,
        *,
        status: Status = Status.TODO,
        created_at: datetime | None = None,
        completed_at: datetime | None = None,
        id: str | None = None,
    ) -> None:
        # Дедлайн і статус тут не перевіряються, щоб можна було відновити збережений стан.
        self._id = id or str(uuid.uuid4())
        self._title = title
        self._description = description
        self._priority = priority
        self._deadline = deadline
        self._status = status
        self._created_at = created_at or datetime.now()
        self._completed_at = completed_at
        self._assignee: TeamMember | None = None
        self._previous_status: Status | None = None

    @property
    def id(self) -> str:
        return self._id

    @property
    def status(self) -> Status:
        return self._status

    @property
    def assignee(self) -> TeamMember | None:
        return self._assignee

    @property
    def deadline(self) -> datetime | None:
        return self._deadline

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        raise NotImplementedError

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        raise NotImplementedError

    @property
    def priority(self) -> Priority:
        return self._priority

    @priority.setter
    def priority(self, value: Priority) -> None:
        raise NotImplementedError

    def allowed_transitions(self) -> frozenset[Status]:
        raise NotImplementedError

    # TODO: @log_status_change з analytics/decorators.py (Напрям 3)
    def change_status(self, new_status: Status) -> None:
        """Перехід за ALLOWED_TRANSITIONS; при DONE ставить completed_at.

        Raises:
            InvalidStatusTransitionError
        """
        raise NotImplementedError

    def assign_to(self, member: TeamMember | None) -> None:
        """Оновлює обидві сторони звʼязку. Членство в проєкті не перевіряє."""
        raise NotImplementedError

    def set_deadline(self, deadline: datetime | None, *, now: datetime | None = None) -> None:
        """Raises: DeadlineInPastError"""
        raise NotImplementedError

    def is_overdue(self, now: datetime | None = None) -> bool:
        """DONE і CANCELLED ніколи не прострочені."""
        raise NotImplementedError

    def get_notification_message(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"Task(id={self._id!r}, title={self._title!r}, status={self._status.value})"
