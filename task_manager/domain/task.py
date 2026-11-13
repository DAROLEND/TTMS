from __future__ import annotations

import uuid
from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from task_manager.analytics.decorators import log_status_change
from task_manager.domain.enums import Priority, Status
from task_manager.domain.notifiable import Notifiable
from task_manager.exceptions import DeadlineInPastError, InvalidStatusTransitionError, ValidationError

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
        # Дедлайн і статус тут не перевіряються на бізнес-правила,
        # щоб можна було відновити збережений стан.
        if not isinstance(status, Status):
            raise ValidationError("status", f"очікується Status, отримано {status!r}")
        self._id = id or str(uuid.uuid4())
        self.title = title
        self.description = description
        self.priority = priority
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
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("title", "назва не може бути порожньою")
        self._title = value.strip()

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValidationError("description", "опис має бути рядком")
        self._description = value

    @property
    def priority(self) -> Priority:
        return self._priority

    @priority.setter
    def priority(self, value: Priority) -> None:
        if not isinstance(value, Priority):
            raise ValidationError("priority", f"очікується Priority, отримано {value!r}")
        self._priority = value

    def allowed_transitions(self) -> frozenset[Status]:
        return self.ALLOWED_TRANSITIONS[self._status]

    @log_status_change
    def change_status(self, new_status: Status) -> None:
        """Перехід за ALLOWED_TRANSITIONS; при DONE ставить completed_at.

        Raises:
            InvalidStatusTransitionError
        """
        if not isinstance(new_status, Status):
            raise ValidationError("status", f"очікується Status, отримано {new_status!r}")
        allowed = self.allowed_transitions()
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                self._id,
                self._status,
                new_status,
                task_title=self._title,
                allowed=[status for status in Status if status in allowed],
            )
        self._previous_status = self._status
        self._status = new_status
        if new_status is Status.DONE:
            self._completed_at = datetime.now()

    def assign_to(self, member: TeamMember | None) -> None:
        """Оновлює обидві сторони звʼязку. Членство в проєкті не перевіряє."""
        if member is self._assignee:
            return
        if self._assignee is not None:
            self._assignee._detach_task(self)
        self._assignee = member
        if member is not None:
            member._attach_task(self)

    def set_deadline(self, deadline: datetime | None, *, now: datetime | None = None) -> None:
        """Raises: DeadlineInPastError"""
        if deadline is not None and deadline < (now or datetime.now()):
            raise DeadlineInPastError(deadline, self._title)
        self._deadline = deadline

    def is_overdue(self, now: datetime | None = None) -> bool:
        """DONE і CANCELLED ніколи не прострочені."""
        if self._deadline is None or self._status.is_final:
            return False
        return (now or datetime.now()) > self._deadline

    def get_notification_message(self) -> str:
        if self._previous_status is None:
            return f"Завдання '{self._title}': статус {self._status.value}"
        return (
            f"Завдання '{self._title}' змінило статус: "
            f"{self._previous_status.value} → {self._status.value}"
        )

    def __repr__(self) -> str:
        return f"Task(id={self._id!r}, title={self._title!r}, status={self._status.value})"
