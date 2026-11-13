"""Демонстрація доменного шару. Запуск: python -m scripts.demo_domain"""

from datetime import datetime, timedelta

from task_manager.analytics.decorators import setup_status_logger
from task_manager.domain import Notifiable, Priority, Project, Status, Task, TeamMember
from task_manager.exceptions import TaskManagerError

LOG_FILE = "logs/status_changes.log"


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    setup_status_logger(LOG_FILE)
    now = datetime.now()

    project = Project("Курсова: таск-менеджер", deadline=now + timedelta(days=14))
    olena = TeamMember("Олена", "olena@example.com", "Developer")
    ivan = TeamMember("Іван", "ivan@example.com", "QA")
    project.add_member(olena)
    project.add_member(ivan)

    login = Task("Сторінка логіну", priority=Priority.HIGH, deadline=now + timedelta(days=3))
    report = Task("Звіт для викладача", priority=Priority.LOW, deadline=now - timedelta(days=1))
    tests = Task("Тести серіалізації", priority=Priority.CRITICAL)
    for task in (login, report, tests):
        project.add_task(task)

    section("Призначення")
    project.assign_task(login.id, olena.id)
    project.assign_task(report.id, olena.id)
    project.assign_task(tests.id, ivan.id)
    for member in project.members:
        print(f"  {member.name}: {[task.title for task in member.assigned_tasks]}")

    project.assign_task(report.id, ivan.id)
    print("  Після перепризначення звіту на Івана:")
    for member in project.members:
        print(f"  {member.name}: {[task.title for task in member.assigned_tasks]}")
    print(f"  report.assignee = {report.assignee.name}")

    section("Переходи статусів")
    for status in (Status.IN_PROGRESS, Status.REVIEW, Status.IN_PROGRESS, Status.REVIEW, Status.DONE):
        login.change_status(status)
        print(f"  {login.title}: → {status.value}")
    print(f"  completed_at = {login.completed_at:%Y-%m-%d %H:%M}")
    tests.change_status(Status.IN_PROGRESS)

    section("Невалідні операції")
    attempts = [
        ("DONE → TODO", lambda: login.change_status(Status.TODO)),
        ("IN_PROGRESS → DONE", lambda: tests.change_status(Status.DONE)),
        ("неіснуючий учасник", lambda: project.assign_task(tests.id, "no-such-id")),
        ("неіснуюче завдання", lambda: project.get_task("no-such-id")),
        ("дедлайн у минулому", lambda: tests.set_deadline(now - timedelta(days=1))),
        ("порожня назва", lambda: Task("   ")),
        ("некоректний email", lambda: TeamMember("Петро", "petro-at-mail")),
    ]
    for name, action in attempts:
        try:
            action()
        except TaskManagerError as err:
            print(f"  {name}: {type(err).__name__}: {err}")

    section("Стан проєкту")
    print(f"  Виконано: {project.completion_rate():.0%}")
    for status in Status:
        titles = [task.title for task in project.get_tasks_by_status(status)]
        print(f"  {status.label}: {titles}")
    print(f"  Прострочені: {[task.title for task in project.tasks if task.is_overdue()]}")

    section("Сповіщення (поліморфізм)")
    items: list[Notifiable] = [project, *project.tasks, *project.members]
    for item in items:
        print(f"  [{type(item).__name__}] {item.get_notification_message()}")

    print(f"\nЗміни статусів записано декоратором @log_status_change у {LOG_FILE}")


if __name__ == "__main__":
    main()
