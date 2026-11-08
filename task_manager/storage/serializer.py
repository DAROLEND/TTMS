"""Напрям 2: серіалізація доменних обʼєктів у JSON і назад.

Тут реалізовані task_to_dict / task_from_dict, member_to_dict / member_from_dict,
project_to_dict / project_from_dict, а також save_state(project, path) і
load_state(path) з двопрохідним відновленням звʼязків та атомарним записом.
Формат словників відповідає docs/CONTRACTS.md, розділ 8 «Формат to_dict()».
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from task_manager.domain.enums import Priority, Status
from task_manager.domain.project import Project
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember
from task_manager.exceptions import StorageError, TaskManagerError

SCHEMA_VERSION = 1


def _parse_optional_datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Поле '{field_name}' має бути рядком ISO або null")
    return datetime.fromisoformat(value)


def _parse_required_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"Поле '{field_name}' має бути рядком ISO")
    return datetime.fromisoformat(value)


def _require_str(data: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    if key not in data:
        raise KeyError(key)
    val = data[key]
    if not isinstance(val, str):
        raise TypeError(f"Поле '{key}' має бути рядком")
    if not allow_empty and not val.strip():
        raise ValueError(f"Поле '{key}' не може бути порожнім")
    return val


def task_to_dict(task: Task) -> dict[str, Any]:
    """Перетворює обʼєкт Task у словник для JSON (посилання на виконавця лише за id)."""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "priority": task.priority.value,
        "assignee_id": task.assignee.id if task.assignee is not None else None,
        "deadline": task.deadline.isoformat() if task.deadline is not None else None,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at is not None else None,
    }


def task_from_dict(data: dict[str, Any]) -> Task:
    """Створює обʼєкт Task зі словника без привʼязки виконавця (Прохід 1)."""
    if not isinstance(data, dict):
        raise TypeError("Очікувався словник для Task")

    task_id = _require_str(data, "id")
    title = _require_str(data, "title")
    description = _require_str(data, "description", allow_empty=True)
    status = Status(_require_str(data, "status"))
    priority = Priority(_require_str(data, "priority"))

    deadline = _parse_optional_datetime(data.get("deadline"), "deadline")
    created_at = _parse_required_datetime(data["created_at"], "created_at")
    completed_at = _parse_optional_datetime(data.get("completed_at"), "completed_at")

    assignee_id = data.get("assignee_id")
    if assignee_id is not None and not isinstance(assignee_id, str):
        raise TypeError("Поле 'assignee_id' має бути рядком або null")

    return Task(
        title=title,
        description=description,
        priority=priority,
        deadline=deadline,
        status=status,
        created_at=created_at,
        completed_at=completed_at,
        id=task_id,
    )


def member_to_dict(member: TeamMember) -> dict[str, Any]:
    """Перетворює обʼєкт TeamMember у словник для JSON."""
    return {
        "id": member.id,
        "name": member.name,
        "email": member.email,
        "role": member.role,
        "task_ids": [task.id for task in member.assigned_tasks],
    }


def member_from_dict(data: dict[str, Any]) -> TeamMember:
    """Створює обʼєкт TeamMember зі словника без призначених завдань (Прохід 1)."""
    if not isinstance(data, dict):
        raise TypeError("Очікувався словник для TeamMember")

    member_id = _require_str(data, "id")
    name = _require_str(data, "name")
    email = _require_str(data, "email")
    role = _require_str(data, "role", allow_empty=True)

    if "@" not in email:
        raise ValueError(f"Некоректний email учасника: '{email}'")

    task_ids = data.get("task_ids", [])
    if not isinstance(task_ids, list) or not all(isinstance(tid, str) for tid in task_ids):
        raise TypeError("Поле 'task_ids' має бути списком рядків")

    return TeamMember(name=name, email=email, role=role, id=member_id)


def project_to_dict(project: Project) -> dict[str, Any]:
    """Перетворює обʼєкт Project у словник для JSON."""
    return {
        "id": project.id,
        "name": project.name,
        "deadline": project.deadline.isoformat() if project.deadline is not None else None,
        "members": [member_to_dict(m) for m in project.members],
        "tasks": [task_to_dict(t) for t in project.tasks],
    }


def project_from_dict(data: dict[str, Any]) -> Project:
    """Двопрохідне відновлення Project зі словника з перевіркою узгодженості звʼязків."""
    if not isinstance(data, dict):
        raise TypeError("Очікувався словник для Project")

    project_id = _require_str(data, "id")
    name = _require_str(data, "name")
    deadline = _parse_optional_datetime(data.get("deadline"), "deadline")

    members_raw = data["members"]
    tasks_raw = data["tasks"]
    if not isinstance(members_raw, list) or not isinstance(tasks_raw, list):
        raise TypeError("Поля 'members' і 'tasks' мають бути списками")

    project = Project(name=name, deadline=deadline, id=project_id)

    # Прохід 1: створення обʼєктів без звʼязків
    for m_data in members_raw:
        member = member_from_dict(m_data)
        project.add_member(member)

    expected_assignees: dict[str, str | None] = {}
    for t_data in tasks_raw:
        task = task_from_dict(t_data)
        project.add_task(task)
        expected_assignees[task.id] = t_data.get("assignee_id")

    # Прохід 2: відновлення двосторонніх звʼязків у порядку task_ids учасників
    assigned_by_member: dict[str, str] = {}
    for m_data in members_raw:
        m_id = m_data["id"]
        for t_id in m_data.get("task_ids", []):
            if t_id in assigned_by_member:
                raise ValueError(f"Завдання '{t_id}' вказано у кількох учасників одночасно")
            project.assign_task(t_id, m_id)
            assigned_by_member[t_id] = m_id

    # Якщо у файлі звʼязок заданий лише через assignee_id (наприклад, демо-дані без task_ids),
    # або перевірка узгодженості між task_ids і assignee_id:
    for task in project.tasks:
        expected_m_id = expected_assignees.get(task.id)
        actual_m_id = task.assignee.id if task.assignee is not None else None

        if actual_m_id is None and expected_m_id is not None:
            # Якщо у члена не було перелічено task_ids, але завдання має assignee_id,
            # перевіряємо, чи у цього учасника взагалі порожній список task_ids у JSON
            member_entry = next((m for m in members_raw if m.get("id") == expected_m_id), None)
            if member_entry is not None and "task_ids" not in member_entry:
                project.assign_task(task.id, expected_m_id)
                actual_m_id = task.assignee.id if task.assignee is not None else None

        if actual_m_id != expected_m_id:
            raise ValueError(
                f"Неузгодженість звʼязків для завдання '{task.id}': "
                f"assignee_id={expected_m_id!r}, але за task_ids призначено {actual_m_id!r}"
            )

    return project


def save_state(project: Project, path: str | os.PathLike[str] = "data/state.json") -> None:
    """Атомарно зберігає стан проєкту у JSON-файл."""
    file_path = Path(path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "project": project_to_dict(project),
    }

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(file_path.parent),
            prefix=f".{file_path.name}.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
                tmp_file.write("\n")
            os.replace(tmp_name, file_path)
        except Exception:
            if os.path.exists(tmp_name):
                try:
                    os.remove(tmp_name)
                except OSError:
                    pass
            raise
    except TaskManagerError as exc:
        raise StorageError(file_path, str(exc)) from exc
    except (OSError, TypeError, ValueError) as exc:
        raise StorageError(file_path, f"не вдалося зберегти файл ({exc})") from exc


def load_state(path: str | os.PathLike[str] = "data/state.json") -> Project:
    """Завантажує стан проєкту з JSON-файлу та відновлює обʼєкти й звʼязки."""
    file_path = Path(path)
    if not file_path.is_file():
        raise StorageError(file_path, "файл не знайдено")

    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StorageError(file_path, f"не вдалося прочитати файл ({exc})") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise StorageError(file_path, "некоректний JSON") from exc

    if not isinstance(payload, dict):
        raise StorageError(file_path, "корінь JSON має бути обʼєктом")

    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise StorageError(
            file_path,
            f"непідтримувана версія схеми: {version!r} (очікувалась {SCHEMA_VERSION})",
        )

    if "project" not in payload:
        raise StorageError(file_path, "відсутній ключ 'project'")

    try:
        return project_from_dict(payload["project"])
    except (KeyError, ValueError, TypeError, TaskManagerError) as exc:
        raise StorageError(file_path, f"некоректні дані проєкту ({exc})") from exc
