"""Тести для Напряму 3: декоратор @log_status_change та Pandas-аналітика.

Запуск: python -m pytest tests/test_analytics.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from task_manager.analytics.decorators import (
    log_status_change,
    read_status_logs,
    setup_status_logger,
)
from task_manager.analytics.stats import (
    get_member_workload,
    get_on_time_completion_stats,
    get_priority_distribution,
    get_priority_status_matrix,
    get_project_summary,
    tasks_to_dataframe,
)
from task_manager.domain.enums import Priority, Status


class _MockTask:
    """Мінімальний мок для Task з публічними атрибутами (CONTRACTS.md §9)."""

    def __init__(self, task_id, title, status, priority, deadline=None, completed_at=None, assignee=None):
        self.id = task_id
        self.title = title
        self.status = status
        self.priority = priority
        self.deadline = deadline
        self.completed_at = completed_at
        self.created_at = datetime.now() - timedelta(days=5)
        self.assignee = assignee

    def is_overdue(self, now=None):
        now = now or datetime.now()
        if self.status in (Status.DONE, Status.CANCELLED):
            return False
        return self.deadline is not None and self.deadline < now

    @log_status_change
    def change_status(self, new_status):
        if self.status == Status.DONE:
            raise ValueError("Перехід із DONE заборонений")
        self.status = new_status


class _MockMember:
    def __init__(self, member_id, name):
        self.id = member_id
        self.name = name


def _make_project_dict():
    now = datetime.now()
    return {
        "schema_version": 1,
        "project": {
            "id": "proj-test", "name": "Тестовий проєкт",
            "deadline": (now + timedelta(days=30)).isoformat(),
            "members": [
                {"id": "u1", "name": "Іван Іваненко", "email": "ivan@test.ua", "role": "Dev", "task_ids": ["t1", "t2"]},
                {"id": "u2", "name": "Олена Петренко", "email": "olena@test.ua", "role": "QA", "task_ids": ["t3", "t4"]},
            ],
            "tasks": [
                {"id": "t1", "title": "Завдання-1 (DONE вчасно)", "description": "OK",
                 "status": "DONE", "priority": "CRITICAL", "assignee_id": "u1",
                 "created_at": (now - timedelta(days=10)).isoformat(),
                 "deadline": (now - timedelta(days=2)).isoformat(),
                 "completed_at": (now - timedelta(days=3)).isoformat()},
                {"id": "t2", "title": "Завдання-2 (DONE із запізненням)", "description": "Late",
                 "status": "DONE", "priority": "HIGH", "assignee_id": "u1",
                 "created_at": (now - timedelta(days=8)).isoformat(),
                 "deadline": (now - timedelta(days=5)).isoformat(),
                 "completed_at": (now - timedelta(days=2)).isoformat()},
                {"id": "t3", "title": "Завдання-3 (IN_PROGRESS, прострочено)", "description": "Overdue",
                 "status": "IN_PROGRESS", "priority": "MEDIUM", "assignee_id": "u2",
                 "created_at": (now - timedelta(days=6)).isoformat(),
                 "deadline": (now - timedelta(days=1)).isoformat(), "completed_at": None},
                {"id": "t4", "title": "Завдання-4 (TODO, у графіку)", "description": "On track",
                 "status": "TODO", "priority": "LOW", "assignee_id": "u2",
                 "created_at": (now - timedelta(days=2)).isoformat(),
                 "deadline": (now + timedelta(days=5)).isoformat(), "completed_at": None},
                {"id": "t5", "title": "Завдання-5 (CANCELLED)", "description": "Cancelled",
                 "status": "CANCELLED", "priority": "LOW", "assignee_id": None,
                 "created_at": (now - timedelta(days=3)).isoformat(),
                 "deadline": None, "completed_at": None},
            ],
        },
    }


class TestLogStatusChange:
    def test_successful_transition_is_logged(self, tmp_path):
        log_file = tmp_path / "test_status.log"
        setup_status_logger(log_file)
        task = _MockTask("abc-123", "Тест декоратора", Status.TODO, Priority.HIGH)
        task.change_status(Status.IN_PROGRESS)
        assert task.status == Status.IN_PROGRESS
        entries = read_status_logs(log_file)
        assert len(entries) >= 1
        assert "TODO -> IN_PROGRESS" in entries[-1]["message"]

    def test_failed_transition_is_logged_and_raised(self, tmp_path):
        log_file = tmp_path / "test_status_err.log"
        setup_status_logger(log_file)
        task = _MockTask("err-001", "Заблокований перехід", Status.DONE, Priority.MEDIUM)
        with pytest.raises(ValueError, match="DONE заборонений"):
            task.change_status(Status.TODO)
        entries = read_status_logs(log_file)
        warning_entries = [e for e in entries if e["level"] == "WARNING"]
        assert len(warning_entries) >= 1
        assert "невдала спроба" in warning_entries[-1]["message"]

    def test_functools_wraps_preserves_metadata(self):
        assert _MockTask.change_status.__name__ == "change_status"

    def test_read_status_logs_nonexistent_file(self, tmp_path):
        result = read_status_logs(tmp_path / "no_such_file.log")
        assert result == []


class TestTasksToDataframe:
    def test_from_dict_project(self):
        df = tasks_to_dataframe(_make_project_dict())
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5

    def test_from_mock_objects(self):
        m = _MockMember("u1", "Іван")
        tasks = [
            _MockTask("t1", "A", Status.TODO, Priority.HIGH, assignee=m),
            _MockTask("t2", "B", Status.DONE, Priority.LOW, completed_at=datetime.now()),
        ]
        df = tasks_to_dataframe(tasks)
        assert len(df) == 2
        assert df.iloc[0]["assignee_name"] == "Іван"

    def test_empty_input(self):
        df = tasks_to_dataframe([])
        assert df.empty
        assert "task_id" in df.columns

    def test_categorical_priority_ordering(self):
        df = tasks_to_dataframe(_make_project_dict())
        assert list(df["priority"].cat.categories) == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_is_overdue_done_always_false(self):
        df = tasks_to_dataframe(_make_project_dict())
        assert not df[df["status"].isin(["DONE", "CANCELLED"])]["is_overdue"].any()

    def test_is_on_time_calculation(self):
        df = tasks_to_dataframe(_make_project_dict())
        assert df[df["task_id"] == "t1"].iloc[0]["is_on_time"] is True
        assert df[df["task_id"] == "t2"].iloc[0]["is_on_time"] is False

    def test_passthrough_dataframe(self):
        orig = pd.DataFrame({"task_id": ["x"], "title": ["Y"]})
        result = tasks_to_dataframe(orig)
        assert result.equals(orig)
        assert result is not orig


class TestMemberWorkload:
    def test_workload_counts(self):
        wl = get_member_workload(_make_project_dict())
        ivan = wl[wl["member_name"] == "Іван Іваненко"].iloc[0]
        assert ivan["done"] == 2
        assert ivan["active_tasks"] == 0
        olena = wl[wl["member_name"] == "Олена Петренко"].iloc[0]
        assert olena["active_tasks"] == 2
        assert olena["overdue"] == 1

    def test_empty_input(self):
        assert get_member_workload([]).empty


class TestOnTimeCompletion:
    def test_completion_counts(self):
        stats = get_on_time_completion_stats(_make_project_dict())
        assert stats["total_completed"] == 2
        assert stats["completed_on_time"] == 1
        assert stats["completed_late"] == 1
        assert stats["on_time_rate_pct"] == 50.0
        assert stats["open_overdue"] == 1

    def test_empty_input(self):
        stats = get_on_time_completion_stats([])
        assert stats["total_completed"] == 0


class TestPriorityDistribution:
    def test_all_priorities_present(self):
        dist = get_priority_distribution(_make_project_dict())
        assert len(dist) == 4
        assert list(dist["priority"]) == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_empty_input(self):
        assert get_priority_distribution([]).empty


class TestProjectSummary:
    def test_completion_rate_excludes_cancelled(self):
        summary = get_project_summary(_make_project_dict())
        assert summary["total_tasks"] == 5
        assert summary["completed_tasks"] == 2
        assert summary["completion_rate_pct"] == 50.0

    def test_empty_input(self):
        assert get_project_summary([])["total_tasks"] == 0
