from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from task_manager.domain.notifiable import Notifiable
from task_manager.exceptions import ValidationError

if TYPE_CHECKING:
    from task_manager.domain.task import Task

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TeamMember(Notifiable):
    def __init__(self, name: str, email: str, role: str = "", *, id: str | None = None) -> None:
        self._id = id or str(uuid.uuid4())
        self.name = name
        self.email = email
        self.role = role
        self._assigned_tasks: list[Task] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def assigned_tasks(self) -> tuple[Task, ...]:
        return tuple(self._assigned_tasks)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError("name", "імʼя не може бути порожнім")
        self._name = value.strip()

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        if not isinstance(value, str) or not _EMAIL_PATTERN.match(value.strip()):
            raise ValidationError("email", f"'{value}' не схожий на email")
        self._email = value.strip()

    @property
    def role(self) -> str:
        return self._role

    @role.setter
    def role(self, value: str) -> None:
        if not isinstance(value, str):
            raise ValidationError("role", "роль має бути рядком")
        self._role = value.strip()

    def active_tasks(self) -> list[Task]:
        return [task for task in self._assigned_tasks if not task.status.is_final]

    def get_notification_message(self) -> str:
        if not self._assigned_tasks:
            return f"{self._name}: призначених завдань немає"
        last = self._assigned_tasks[-1]
        return (
            f"{self._name}, вам призначено завдання '{last.title}' "
            f"(активних: {len(self.active_tasks())})"
        )

    # Викликаються тільки з Task.assign_to(), щоб обидві сторони звʼязку не розійшлися.
    def _attach_task(self, task: Task) -> None:
        if task not in self._assigned_tasks:
            self._assigned_tasks.append(task)

    def _detach_task(self, task: Task) -> None:
        if task in self._assigned_tasks:
            self._assigned_tasks.remove(task)

    def __repr__(self) -> str:
        return f"TeamMember(id={self._id!r}, name={self._name!r}, email={self._email!r})"
