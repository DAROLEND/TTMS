"""Напрям 2: спільні фікстури pytest (готовий проєкт з учасниками й завданнями)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from task_manager.domain.enums import Priority, Status
from task_manager.domain.project import Project
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember


@pytest.fixture
def base_now() -> datetime:
    """Фіксована точка часу для детермінованих тестів дедлайнів."""
    return datetime(2026, 11, 1, 12, 0, 0)


@pytest.fixture
def sample_members() -> tuple[TeamMember, TeamMember]:
    """Двоє учасників команди для тестів."""
    dev = TeamMember(
        name="Олександр Шевченко",
        email="o.shevchenko@example.com",
        role="Backend Developer",
        id="member-dev-1",
    )
    qa = TeamMember(
        name="Марія Коваль",
        email="m.koval@example.com",
        role="QA Engineer",
        id="member-qa-2",
    )
    return dev, qa


@pytest.fixture
def sample_tasks(base_now: datetime) -> tuple[Task, Task, Task]:
    """Три завдання з різними статусами, пріоритетами та дедлайнами."""
    t_todo = Task(
        title="Реалізувати серіалізацію JSON",
        description="Написати save_state та load_state",
        priority=Priority.HIGH,
        deadline=base_now + timedelta(days=5),
        status=Status.TODO,
        created_at=base_now - timedelta(days=2),
        id="task-todo-1",
    )
    t_in_progress = Task(
        title="Покрити домен тестами",
        description="Перевірити переходи статусів та дедлайни",
        priority=Priority.CRITICAL,
        deadline=base_now - timedelta(days=1),
        status=Status.IN_PROGRESS,
        created_at=base_now - timedelta(days=4),
        id="task-prog-2",
    )
    t_done = Task(
        title="Узгодити контракти проєкту",
        description="Описати публічні сигнатури у CONTRACTS.md",
        priority=Priority.MEDIUM,
        deadline=base_now - timedelta(days=2),
        status=Status.DONE,
        created_at=base_now - timedelta(days=7),
        completed_at=base_now - timedelta(days=3),
        id="task-done-3",
    )
    return t_todo, t_in_progress, t_done


@pytest.fixture
def empty_project(base_now: datetime) -> Project:
    """Порожній проєкт без учасників і завдань."""
    return Project(
        name="TTMS: Система управління завданнями",
        deadline=base_now + timedelta(days=30),
        id="project-main-1",
    )


@pytest.fixture
def populated_project(
    empty_project: Project,
    sample_members: tuple[TeamMember, TeamMember],
    sample_tasks: tuple[Task, Task, Task],
) -> Project:
    """Готовий проєкт з учасниками, завданнями та встановленими звʼязками."""
    dev, qa = sample_members
    t_todo, t_in_progress, t_done = sample_tasks

    empty_project.add_member(dev)
    empty_project.add_member(qa)

    empty_project.add_task(t_todo)
    empty_project.add_task(t_in_progress)
    empty_project.add_task(t_done)

    empty_project.assign_task(t_todo.id, dev.id)
    empty_project.assign_task(t_in_progress.id, qa.id)
    empty_project.assign_task(t_done.id, dev.id)

    return empty_project
