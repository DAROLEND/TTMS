"""Напрям 2: тести серіалізації в JSON, round-trip збереження та обробки StorageError."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from task_manager.domain.enums import Priority, Status
from task_manager.domain.project import Project
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember
from task_manager.exceptions import StorageError
from task_manager.storage.serializer import (
    SCHEMA_VERSION,
    load_state,
    member_from_dict,
    member_to_dict,
    project_from_dict,
    project_to_dict,
    save_state,
    task_from_dict,
    task_to_dict,
)


class TestEntitySerialization:
    """Модульні тести конвертації окремих сутностей у словник і назад."""

    def test_task_to_dict_and_from_dict(self, base_now: datetime) -> None:
        task = Task(
            title="Перевірка серіалізації",
            description="Опис завдання",
            priority=Priority.HIGH,
            deadline=base_now,
            status=Status.REVIEW,
            created_at=base_now,
            completed_at=None,
            id="task-ser-1",
        )
        data = task_to_dict(task)
        assert data == {
            "id": "task-ser-1",
            "title": "Перевірка серіалізації",
            "description": "Опис завдання",
            "status": "REVIEW",
            "priority": "HIGH",
            "assignee_id": None,
            "deadline": base_now.isoformat(),
            "created_at": base_now.isoformat(),
            "completed_at": None,
        }

        restored = task_from_dict(data)
        assert task_to_dict(restored) == data

    def test_member_to_dict_and_from_dict(self) -> None:
        member = TeamMember(
            name="Ірина Бондар",
            email="i.bondar@example.com",
            role="Designer",
            id="member-ser-1",
        )
        data = member_to_dict(member)
        assert data == {
            "id": "member-ser-1",
            "name": "Ірина Бондар",
            "email": "i.bondar@example.com",
            "role": "Designer",
            "task_ids": [],
        }

        restored = member_from_dict(data)
        assert member_to_dict(restored) == data


class TestRoundTripStorage:
    """Тести повного циклу збереження та двопрохідного завантаження проєкту."""

    def test_project_round_trip_preserves_all_fields_and_relations(
        self, populated_project: Project, tmp_path: Path
    ) -> None:
        state_file = tmp_path / "state.json"
        original_dict = project_to_dict(populated_project)

        save_state(populated_project, state_file)
        assert state_file.is_file()

        raw_payload = json.loads(state_file.read_text(encoding="utf-8"))
        assert raw_payload["schema_version"] == SCHEMA_VERSION

        loaded_project = load_state(state_file)
        assert project_to_dict(loaded_project) == original_dict

        # Перевірка відновлення двосторонніх посилань в обʼєктах
        dev = loaded_project.get_member("member-dev-1")
        t_todo = loaded_project.get_task("task-todo-1")
        assert t_todo.assignee is dev
        assert t_todo in dev.assigned_tasks

    def test_empty_project_round_trip(self, empty_project: Project, tmp_path: Path) -> None:
        state_file = tmp_path / "empty_state.json"
        save_state(empty_project, state_file)
        loaded = load_state(state_file)
        assert project_to_dict(loaded) == project_to_dict(empty_project)
        assert len(loaded.tasks) == 0
        assert len(loaded.members) == 0


class TestStorageErrors:
    """Тести обробки пошкоджених файлів і некоректних даних сховища."""

    def test_load_nonexistent_file_raises_storage_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.json"
        with pytest.raises(StorageError) as exc_info:
            load_state(missing)
        assert "файл не знайдено" in str(exc_info.value)

    def test_load_corrupted_json_raises_storage_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "corrupted.json"
        bad_file.write_text("{invalid json: [1, 2", encoding="utf-8")

        with pytest.raises(StorageError) as exc_info:
            load_state(bad_file)
        assert "некоректний JSON" in str(exc_info.value)

    def test_load_unsupported_schema_version_raises_storage_error(
        self, tmp_path: Path
    ) -> None:
        bad_version_file = tmp_path / "wrong_version.json"
        bad_version_file.write_text(
            json.dumps({"schema_version": 999, "project": {}}),
            encoding="utf-8",
        )
        with pytest.raises(StorageError) as exc_info:
            load_state(bad_version_file)
        assert "непідтримувана версія схеми" in str(exc_info.value)

    def test_load_missing_project_key_raises_storage_error(self, tmp_path: Path) -> None:
        no_proj_file = tmp_path / "no_project.json"
        no_proj_file.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

        with pytest.raises(StorageError) as exc_info:
            load_state(no_proj_file)
        assert "відсутній ключ 'project'" in str(exc_info.value)

    def test_inconsistent_assignee_links_raise_storage_error(
        self, tmp_path: Path
    ) -> None:
        broken_links_file = tmp_path / "broken_links.json"
        payload = {
            "schema_version": 1,
            "project": {
                "id": "p-1",
                "name": "Биті звʼязки",
                "deadline": None,
                "members": [
                    {
                        "id": "m-1",
                        "name": "Олена",
                        "email": "olena@example.com",
                        "role": "Dev",
                        "task_ids": ["t-1"],
                    }
                ],
                "tasks": [
                    {
                        "id": "t-1",
                        "title": "Завдання з іншим assignee_id",
                        "description": "",
                        "status": "TODO",
                        "priority": "LOW",
                        "assignee_id": None,  # Суперечить task_ids учасника m-1
                        "deadline": None,
                        "created_at": "2026-10-20T10:00:00",
                        "completed_at": None,
                    }
                ],
            },
        }
        broken_links_file.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(StorageError):
            load_state(broken_links_file)

    def test_invalid_enum_value_in_json_raises_storage_error(
        self, tmp_path: Path
    ) -> None:
        bad_enum_file = tmp_path / "bad_enum.json"
        payload = {
            "schema_version": 1,
            "project": {
                "id": "p-1",
                "name": "Невірний статус",
                "deadline": None,
                "members": [],
                "tasks": [
                    {
                        "id": "t-1",
                        "title": "Завдання",
                        "description": "",
                        "status": "UNKNOWN_STATUS",
                        "priority": "LOW",
                        "assignee_id": None,
                        "deadline": None,
                        "created_at": "2026-10-20T10:00:00",
                        "completed_at": None,
                    }
                ],
            },
        }
        bad_enum_file.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(StorageError):
            load_state(bad_enum_file)
