from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from task_manager.domain.notifiable import Notifiable

if TYPE_CHECKING:
    from task_manager.domain.task import Task


class TeamMember(Notifiable):
    def __init__(self, name: str, email: str, role: str = "", *, id: str | None = None) -> None:
        self._id = id or str(uuid.uuid4())
        self._name = name
        self._email = email
        self._role = role
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
        raise NotImplementedError

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, value: str) -> None:
        raise NotImplementedError

    @property
    def role(self) -> str:
        return self._role

    @role.setter
    def role(self, value: str) -> None:
        raise NotImplementedError

    def active_tasks(self) -> list[Task]:
        raise NotImplementedError

    def get_notification_message(self) -> str:
        raise NotImplementedError

    # Викликаються тільки з Task.assign_to(), щоб обидві сторони звʼязку не розійшлися.
    def _attach_task(self, task: Task) -> None:
        raise NotImplementedError

    def _detach_task(self, task: Task) -> None:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"TeamMember(id={self._id!r}, name={self._name!r}, email={self._email!r})"
