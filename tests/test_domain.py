"""Напрям 2: тести логіки зміни статусів, дедлайнів, призначення учасників і валідації.

Тести написані строго за контрактами docs/CONTRACTS.md.
Матриця переходів статусів захардкоджена в тесті, щоб перевіряти специфікацію незалежно.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from task_manager.domain.enums import Priority, Status
from task_manager.domain.notifiable import Notifiable
from task_manager.domain.project import Project
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember
from task_manager.exceptions import (
    DeadlineInPastError,
    InvalidStatusTransitionError,
    MemberNotFoundError,
    TaskNotFoundError,
    ValidationError,
)

# Специфікація переходів за docs/CONTRACTS.md (§2)
VALID_TRANSITIONS: list[tuple[Status, Status]] = [
    (Status.TODO, Status.IN_PROGRESS),
    (Status.TODO, Status.CANCELLED),
    (Status.IN_PROGRESS, Status.REVIEW),
    (Status.IN_PROGRESS, Status.CANCELLED),
    (Status.REVIEW, Status.DONE),
    (Status.REVIEW, Status.IN_PROGRESS),
    (Status.REVIEW, Status.CANCELLED),
]

ALL_STATUS_PAIRS: list[tuple[Status, Status]] = [
    (src, dst) for src in Status for dst in Status
]
INVALID_TRANSITIONS: list[tuple[Status, Status]] = [
    pair for pair in ALL_STATUS_PAIRS if pair not in VALID_TRANSITIONS
]


class TestStatusTransitions:
    """Тести переходів між статусами завдання."""

    @pytest.mark.parametrize(("initial_status", "target_status"), VALID_TRANSITIONS)
    def test_valid_status_transitions(self, initial_status: Status, target_status: Status) -> None:
        task = Task(title="Перевірка переходу", status=initial_status)
        task.change_status(target_status)

        assert task.status == target_status
        if target_status == Status.DONE:
            assert task.completed_at is not None
            assert isinstance(task.completed_at, datetime)
        else:
            assert task.completed_at is None

    @pytest.mark.parametrize(("initial_status", "target_status"), INVALID_TRANSITIONS)
    def test_invalid_status_transitions_raise_error(
        self, initial_status: Status, target_status: Status
    ) -> None:
        task = Task(title="Невалідний перехід", status=initial_status, id="task-err-1")
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            task.change_status(target_status)

        err = exc_info.value
        assert err.task_id == "task-err-1"
        assert err.current == initial_status
        assert err.target == target_status
        assert task.status == initial_status

    def test_full_lifecycle_todo_to_done(self) -> None:
        task = Task(title="Повний життєвий цикл")
        assert task.status == Status.TODO
        assert task.completed_at is None

        task.change_status(Status.IN_PROGRESS)
        assert task.status == Status.IN_PROGRESS

        task.change_status(Status.REVIEW)
        assert task.status == Status.REVIEW

        # Повернення на доопрацювання
        task.change_status(Status.IN_PROGRESS)
        assert task.status == Status.IN_PROGRESS

        task.change_status(Status.REVIEW)
        task.change_status(Status.DONE)
        assert task.status == Status.DONE
        assert task.completed_at is not None

    def test_allowed_transitions_matches_contract(self) -> None:
        task = Task(title="Перевірка allowed_transitions", status=Status.REVIEW)
        assert task.allowed_transitions() == frozenset(
            {Status.DONE, Status.IN_PROGRESS, Status.CANCELLED}
        )


class TestDeadlines:
    """Тести дедлайнів та прострочення для Task і Project."""

    def test_task_set_deadline_in_future_succeeds(self, base_now: datetime) -> None:
        task = Task(title="Завдання з дедлайном")
        future_deadline = base_now + timedelta(days=3)
        task.set_deadline(future_deadline, now=base_now)
        assert task.deadline == future_deadline

    def test_task_set_deadline_none_clears_deadline(self, base_now: datetime) -> None:
        task = Task(title="Завдання", deadline=base_now + timedelta(days=3))
        task.set_deadline(None, now=base_now)
        assert task.deadline is None

    def test_task_set_deadline_in_past_raises_error(self, base_now: datetime) -> None:
        task = Task(title="Прострочений дедлайн")
        past_deadline = base_now - timedelta(minutes=1)
        with pytest.raises(DeadlineInPastError) as exc_info:
            task.set_deadline(past_deadline, now=base_now)
        assert exc_info.value.deadline == past_deadline

    def test_task_is_overdue_for_active_task_in_past(self, base_now: datetime) -> None:
        task = Task(
            title="Активне прострочене",
            status=Status.IN_PROGRESS,
            deadline=base_now - timedelta(hours=2),
        )
        assert task.is_overdue(now=base_now) is True

    def test_task_is_overdue_false_for_future_or_none_deadline(self, base_now: datetime) -> None:
        task_future = Task(
            title="Майбутнє",
            status=Status.TODO,
            deadline=base_now + timedelta(hours=5),
        )
        task_no_dl = Task(title="Без дедлайну", status=Status.TODO, deadline=None)
        assert task_future.is_overdue(now=base_now) is False
        assert task_no_dl.is_overdue(now=base_now) is False

    @pytest.mark.parametrize("final_status", [Status.DONE, Status.CANCELLED])
    def test_final_statuses_are_never_overdue(
        self, base_now: datetime, final_status: Status
    ) -> None:
        task = Task(
            title="Завершене завдання",
            status=final_status,
            deadline=base_now - timedelta(days=10),
        )
        assert task.is_overdue(now=base_now) is False

    def test_project_set_deadline_and_days_until_deadline(self, base_now: datetime) -> None:
        project = Project(name="Проєкт")
        assert project.days_until_deadline(now=base_now) is None

        target = base_now + timedelta(days=10)
        project.set_deadline(target, now=base_now)
        assert project.deadline == target
        assert project.days_until_deadline(now=base_now) == 10

        with pytest.raises(DeadlineInPastError):
            project.set_deadline(base_now - timedelta(days=1), now=base_now)


class TestProjectAssignmentsAndErrors:
    """Тести обробки помилок призначення, пошуку та валідації."""

    def test_assign_task_to_nonexistent_member_raises_error(
        self, empty_project: Project, sample_tasks: tuple[Task, Task, Task]
    ) -> None:
        t_todo, _, _ = sample_tasks
        empty_project.add_task(t_todo)

        with pytest.raises(MemberNotFoundError) as exc_info:
            empty_project.assign_task(t_todo.id, "non-existent-member-id")
        assert exc_info.value.member_id == "non-existent-member-id"

    def test_assign_nonexistent_task_raises_error(
        self, empty_project: Project, sample_members: tuple[TeamMember, TeamMember]
    ) -> None:
        dev, _ = sample_members
        empty_project.add_member(dev)

        with pytest.raises(TaskNotFoundError) as exc_info:
            empty_project.assign_task("non-existent-task-id", dev.id)
        assert exc_info.value.task_id == "non-existent-task-id"

    def test_add_task_with_foreign_assignee_raises_member_not_found(
        self, empty_project: Project, sample_members: tuple[TeamMember, TeamMember]
    ) -> None:
        outsider, _ = sample_members
        task = Task(title="Зовнішній виконавець")
        task.assign_to(outsider)

        with pytest.raises(MemberNotFoundError):
            empty_project.add_task(task)

    def test_duplicate_task_and_member_id_raise_validation_error(
        self,
        empty_project: Project,
        sample_members: tuple[TeamMember, TeamMember],
        sample_tasks: tuple[Task, Task, Task],
    ) -> None:
        dev, _ = sample_members
        t_todo, _, _ = sample_tasks

        empty_project.add_member(dev)
        with pytest.raises(ValidationError):
            empty_project.add_member(TeamMember(name="Клон", email="c@example.com", id=dev.id))

        empty_project.add_task(t_todo)
        with pytest.raises(ValidationError):
            empty_project.add_task(Task(title="Клон завдання", id=t_todo.id))

    def test_reassign_and_unassign_updates_both_sides(
        self,
        empty_project: Project,
        sample_members: tuple[TeamMember, TeamMember],
        sample_tasks: tuple[Task, Task, Task],
    ) -> None:
        dev, qa = sample_members
        t_todo, _, _ = sample_tasks

        empty_project.add_member(dev)
        empty_project.add_member(qa)
        empty_project.add_task(t_todo)

        empty_project.assign_task(t_todo.id, dev.id)
        assert t_todo.assignee is dev
        assert t_todo in dev.assigned_tasks

        # Перепризначення іншому учаснику
        empty_project.assign_task(t_todo.id, qa.id)
        assert t_todo.assignee is qa
        assert t_todo not in dev.assigned_tasks
        assert t_todo in qa.assigned_tasks

        # Зняття виконавця
        empty_project.unassign_task(t_todo.id)
        assert t_todo.assignee is None
        assert t_todo not in qa.assigned_tasks

    def test_project_completion_rate_and_filter_by_status(
        self, populated_project: Project
    ) -> None:
        # У populated_project: 1 TODO, 1 IN_PROGRESS, 1 DONE -> 1 / 3
        assert populated_project.completion_rate() == pytest.approx(1 / 3)
        done_tasks = populated_project.get_tasks_by_status(Status.DONE)
        assert len(done_tasks) == 1
        assert done_tasks[0].id == "task-done-3"

    def test_validation_errors_on_setters(
        self, sample_members: tuple[TeamMember, TeamMember]
    ) -> None:
        dev, _ = sample_members
        task = Task(title="Валідна назва")

        with pytest.raises(ValidationError):
            task.title = "   "

        with pytest.raises(ValidationError):
            task.priority = "HIGH"  # type: ignore[assignment]

        with pytest.raises(ValidationError):
            dev.name = ""

        with pytest.raises(ValidationError):
            dev.email = "invalid-email-without-at"

    def test_notifiable_polymorphism(self, populated_project: Project) -> None:
        with pytest.raises(TypeError):
            Notifiable()  # type: ignore[abstract]

        entities: list[Notifiable] = [
            populated_project,
            *populated_project.tasks,
            *populated_project.members,
        ]
        for item in entities:
            msg = item.get_notification_message()
            assert isinstance(msg, str)
            assert len(msg.strip()) > 0
