"""
Винятки застосунку

Усі наслідують TaskManagerError
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from task_manager.domain.enums import Status


class TaskManagerError(Exception):
    pass


class ValidationError(TaskManagerError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"Некоректне значення поля '{field}': {message}")


class TaskNotFoundError(TaskManagerError):
    def __init__(self, task_id: str, project_name: str | None = None) -> None:
        self.task_id = task_id
        self.project_name = project_name
        where = f" у проєкті '{project_name}'" if project_name else ""
        super().__init__(f"Завдання з id '{task_id}' не знайдено{where}")


class MemberNotFoundError(TaskManagerError):
    def __init__(self, member_id: str, project_name: str | None = None) -> None:
        self.member_id = member_id
        self.project_name = project_name
        where = f" у проєкті '{project_name}'" if project_name else ""
        super().__init__(f"Учасника з id '{member_id}' не знайдено{where}")


class InvalidStatusTransitionError(TaskManagerError):
    def __init__(
        self,
        task_id: str,
        current: Status,
        target: Status,
        *,
        task_title: str | None = None,
        allowed: Iterable[Status] = (),
    ) -> None:
        self.task_id = task_id
        self.current = current
        self.target = target
        self.allowed = tuple(allowed)
        name = f"'{task_title}'" if task_title else f"з id '{task_id}'"
        allowed_text = ", ".join(s.value for s in self.allowed) or "немає"
        super().__init__(
            f"Неможливо змінити статус завдання {name}: "
            f"{current.value} → {target.value}. "
            f"Дозволені переходи з {current.value}: {allowed_text}"
        )


class DeadlineInPastError(TaskManagerError):
    def __init__(self, deadline: datetime, entity_name: str | None = None) -> None:
        self.deadline = deadline
        self.entity_name = entity_name
        target = f" для '{entity_name}'" if entity_name else ""
        super().__init__(f"Дедлайн {deadline:%Y-%m-%d %H:%M}{target} уже в минулому")


class StorageError(TaskManagerError):
    def __init__(self, path: str | os.PathLike[str], reason: str) -> None:
        self.path = os.fspath(path)
        self.reason = reason
        super().__init__(f"Помилка сховища '{self.path}': {reason}")
