"""Напрям 2: консольний інтерфейс — точка входу застосунку.

Запуск: python -m task_manager.cli
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from task_manager.analytics.decorators import setup_status_logger
from task_manager.domain.enums import Priority, Status
from task_manager.domain.notifiable import Notifiable
from task_manager.domain.project import Project
from task_manager.domain.task import Task
from task_manager.domain.team_member import TeamMember
from task_manager.exceptions import StorageError, TaskManagerError
from task_manager.storage.serializer import load_state, save_state

DEFAULT_STATE_PATH = Path("data/state.json")
DATETIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")


def _prompt_non_empty(prompt_text: str) -> str:
    """Запитує непорожній рядок у користувача."""
    while True:
        value = input(prompt_text).strip()
        if value:
            return value
        print("Помилка: значення не може бути порожнім. Спробуйте ще раз.")


def _prompt_optional_datetime(prompt_text: str) -> datetime | None:
    """Запитує дату/час у форматі YYYY-MM-DD [HH:MM] або порожній рядок для None."""
    while True:
        raw = input(prompt_text).strip()
        if not raw:
            return None
        for fmt in DATETIME_FORMATS:
            try:
                parsed = datetime.strptime(raw, fmt)
                if fmt == "%Y-%m-%d":
                    parsed = parsed.replace(hour=23, minute=59, second=0)
                return parsed
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw).replace(tzinfo=None)
        except ValueError:
            print(
                "Невірний формат дати. Використовуйте YYYY-MM-DD або YYYY-MM-DD HH:MM "
                "(наприклад, 2026-12-15 18:00)."
            )


def _prompt_choice(prompt_text: str, max_index: int) -> int | None:
    """Запитує номер елемента зі списку (1..max_index) або 0 для скасування."""
    while True:
        raw = input(prompt_text).strip()
        if not raw or raw == "0":
            return None
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= max_index:
                return idx
        print(f"Введіть число від 1 до {max_index} (або 0 для скасування).")


def _select_priority() -> Priority:
    """Вибір пріоритету завдання з меню."""
    priorities = list(Priority)
    print("\nДоступні пріоритети:")
    for idx, p in enumerate(priorities, start=1):
        print(f"  {idx}. {p.label} ({p.value})")
    choice = _prompt_choice(
        f"Оберіть пріоритет [1-{len(priorities)}, Enter = {Priority.MEDIUM.label}]: ",
        len(priorities),
    )
    if choice is None:
        return Priority.MEDIUM
    return priorities[choice - 1]


def _select_status(statuses: list[Status], prompt_label: str = "Оберіть статус") -> Status | None:
    """Вибір статусу зі списку дозволених."""
    if not statuses:
        print("Немає доступних статусів для вибору.")
        return None
    print("\nДоступні статуси:")
    for idx, st in enumerate(statuses, start=1):
        print(f"  {idx}. {st.label} ({st.value})")
    choice = _prompt_choice(f"{prompt_label} [1-{len(statuses)}, 0 — скасувати]: ", len(statuses))
    if choice is None:
        return None
    return statuses[choice - 1]


def _select_member(project: Project) -> TeamMember | None:
    """Дозволяє обрати учасника проєкту за номером або ID."""
    members = project.members
    if not members:
        print("У проєкті ще немає жодного учасника.")
        return None

    print("\nУчасники команди:")
    for idx, m in enumerate(members, start=1):
        role_str = f" ({m.role})" if m.role else ""
        print(f"  {idx}. {m.name}{role_str} <{m.email}> [id: {m.id[:8]}]")

    raw = input(f"Оберіть номер учасника [1-{len(members)}] або введіть ID (0 — скасувати): ").strip()
    if not raw or raw == "0":
        return None
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(members):
            return members[idx - 1]
    return project.get_member(raw)


def _select_task(project: Project) -> Task | None:
    """Дозволяє обрати завдання проєкту за номером або ID."""
    tasks = project.tasks
    if not tasks:
        print("У проєкті ще немає жодного завдання.")
        return None

    print("\nЗавдання проєкту:")
    for idx, t in enumerate(tasks, start=1):
        assignee_name = t.assignee.name if t.assignee else "Не призначено"
        print(
            f"  {idx}. [{t.status.label}] {t.title} "
            f"(Пріоритет: {t.priority.label}, Виконавець: {assignee_name}) [id: {t.id[:8]}]"
        )

    raw = input(f"Оберіть номер завдання [1-{len(tasks)}] або введіть ID (0 — скасувати): ").strip()
    if not raw or raw == "0":
        return None
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(tasks):
            return tasks[idx - 1]
    return project.get_task(raw)


def _init_or_load_project(state_path: Path) -> Project:
    """Завантажує існуючий проєкт зі state.json або створює новий."""
    if state_path.is_file():
        try:
            project = load_state(state_path)
            print(f"Стан проєкту '{project.name}' успішно завантажено з '{state_path}'.")
            return project
        except StorageError as err:
            print(f"Попередження: {err}")
            ans = input("Створити новий проєкт замість пошкодженого файлу? (y/n): ").strip().lower()
            if ans not in ("y", "yes", "так", "т"):
                raise SystemExit(1)

    print("\n--- Створення нового проєкту ---")
    name = _prompt_non_empty("Введіть назву проєкту: ")
    deadline = _prompt_optional_datetime("Дедлайн проєкту (YYYY-MM-DD [HH:MM], Enter — пропустити): ")
    project = Project(name=name, deadline=deadline)
    try:
        save_state(project, state_path)
    except StorageError as err:
        print(f"Попередження: не вдалося зберегти початковий стан ({err})")
    return project


def _handle_show_overview(project: Project) -> None:
    """Показує загальну інформацію про проєкт, учасників та всі завдання."""
    print(f"\n=== Проєкт: {project.name} (id: {project.id}) ===")
    dl_str = project.deadline.strftime("%Y-%m-%d %H:%M") if project.deadline else "Не встановлено"
    print(f"Дедлайн проєкту: {dl_str}")
    try:
        rate_pct = round(project.completion_rate() * 100, 1)
        print(f"Прогрес виконання: {rate_pct}%")
    except NotImplementedError:
        pass

    print(f"\nУчасники команди ({len(project.members)}):")
    if not project.members:
        print("  (немає учасників)")
    for idx, m in enumerate(project.members, start=1):
        role_str = f" [{m.role}]" if m.role else ""
        print(f"  {idx}. {m.name}{role_str} — {m.email} (призначено завдань: {len(m.assigned_tasks)})")

    print(f"\nЗавдання ({len(project.tasks)}):")
    if not project.tasks:
        print("  (немає завдань)")
    for idx, t in enumerate(project.tasks, start=1):
        assignee_str = t.assignee.name if t.assignee else "Не призначено"
        dl = t.deadline.strftime("%Y-%m-%d %H:%M") if t.deadline else "—"
        overdue_tag = ""
        try:
            if t.is_overdue():
                overdue_tag = " [ПРОСТРОЧЕНО!]"
        except NotImplementedError:
            pass
        print(
            f"  {idx}. [{t.status.label}] {t.title}{overdue_tag}\n"
            f"      Пріоритет: {t.priority.label} | Виконавець: {assignee_str} | Дедлайн: {dl}"
        )


def _handle_add_member(project: Project) -> None:
    """Додає нового учасника в проєкт."""
    print("\n--- Додавання учасника команди ---")
    name = _prompt_non_empty("Ім'я учасника: ")
    email = _prompt_non_empty("Email учасника: ")
    role = input("Роль у команді (наприклад, Developer, QA): ").strip()

    member = TeamMember(name=name, email=email, role=role)
    project.add_member(member)
    print(f"Учасника '{member.name}' успішно додано до проєкту.")


def _handle_add_task(project: Project) -> None:
    """Створює нове завдання та додає його в проєкт."""
    print("\n--- Створення нового завдання ---")
    title = _prompt_non_empty("Назва завдання: ")
    description = input("Опис завдання (необов'язково): ").strip()
    priority = _select_priority()
    deadline = _prompt_optional_datetime("Дедлайн (YYYY-MM-DD [HH:MM], Enter — без дедлайну): ")

    task = Task(title=title, description=description, priority=priority)
    if deadline is not None:
        task.set_deadline(deadline)

    project.add_task(task)
    print(f"Завдання '{task.title}' успішно створено.")


def _handle_assign_task(project: Project) -> None:
    """Призначає завдання учаснику або знімає виконавця."""
    print("\n--- Призначення виконавця завдання ---")
    task = _select_task(project)
    if task is None:
        return

    print("1. Призначити учасника")
    print("2. Зняти поточного виконавця")
    action = input("Ваш вибір [1/2, Enter — 1]: ").strip() or "1"

    if action == "2":
        project.unassign_task(task.id)
        print(f"Виконавця знято із завдання '{task.title}'.")
        return

    member = _select_member(project)
    if member is None:
        return

    project.assign_task(task.id, member.id)
    print(f"Завдання '{task.title}' призначено учаснику '{member.name}'.")


def _handle_change_status(project: Project) -> None:
    """Змінює статус обраного завдання."""
    print("\n--- Зміна статусу завдання ---")
    task = _select_task(project)
    if task is None:
        return

    print(f"Поточний статус '{task.title}': {task.status.label} ({task.status.value})")
    try:
        allowed = sorted(task.allowed_transitions(), key=lambda s: list(Status).index(s))
    except NotImplementedError:
        allowed = list(Status)

    if not allowed:
        print(f"Статус '{task.status.label}' є фінальним — переходи заборонені.")
        return

    new_status = _select_status(allowed, "Оберіть новий статус")
    if new_status is None:
        return

    task.change_status(new_status)
    print(f"Статус завдання '{task.title}' змінено на '{task.status.label}'.")


def _handle_filter_by_status(project: Project) -> None:
    """Виводить завдання з обраним статусом."""
    print("\n--- Фільтр завдань за статусом ---")
    status = _select_status(list(Status), "Оберіть статус для фільтрації")
    if status is None:
        return

    tasks = project.get_tasks_by_status(status)
    print(f"\nЗавдання зі статусом '{status.label}' ({len(tasks)}):")
    if not tasks:
        print("  (немає завдань)")
    for idx, t in enumerate(tasks, start=1):
        assignee_str = t.assignee.name if t.assignee else "Не призначено"
        print(f"  {idx}. {t.title} [Пріоритет: {t.priority.label}, Виконавець: {assignee_str}]")


def _handle_change_deadline(project: Project) -> None:
    """Оновлює дедлайн завдання або всього проєкту."""
    print("\n--- Зміна дедлайну ---")
    print("1. Змінити дедлайн завдання")
    print("2. Змінити дедлайн проєкту")
    choice = input("Ваш вибір [1/2]: ").strip()

    if choice == "1":
        task = _select_task(project)
        if task is None:
            return
        new_dl = _prompt_optional_datetime("Новий дедлайн (YYYY-MM-DD [HH:MM], Enter — прибрати): ")
        task.set_deadline(new_dl)
        print(f"Дедлайн завдання '{task.title}' оновлено.")
    elif choice == "2":
        new_dl = _prompt_optional_datetime("Новий дедлайн проєкту (YYYY-MM-DD [HH:MM], Enter — прибрати): ")
        project.set_deadline(new_dl)
        print(f"Дедлайн проєкту '{project.name}' оновлено.")


def _handle_show_notifications(project: Project) -> None:
    """Демонструє поліморфізм Notifiable для проєкту, завдань та учасників."""
    print("\n--- Сповіщення системи (Notifiable) ---")
    items: list[Notifiable] = [project, *project.tasks, *project.members]
    for item in items:
        print(f"  • {item.get_notification_message()}")


def main(state_path: Path = DEFAULT_STATE_PATH) -> None:
    """Головний цикл консольного меню."""
    setup_status_logger()
    print("====================================================")
    print("   TTMS: Система управління завданнями команди")
    print("====================================================")

    project = _init_or_load_project(state_path)

    menu_options = (
        "1. Огляд проєкту (учасники та завдання)",
        "2. Додати учасника команди",
        "3. Створити нове завдання",
        "4. Призначити / зняти виконавця завдання",
        "5. Змінити статус завдання",
        "6. Змінити дедлайн завдання або проєкту",
        "7. Фільтрувати завдання за статусом",
        "8. Показати сповіщення (Notifiable)",
        "9. Зберегти стан проєкту",
        "0. Зберегти та вийти",
    )

    while True:
        print("\n---------------- Меню ----------------")
        for line in menu_options:
            print(line)
        choice = input("Оберіть дію [0-9]: ").strip()

        try:
            if choice == "1":
                _handle_show_overview(project)
            elif choice == "2":
                _handle_add_member(project)
                save_state(project, state_path)
            elif choice == "3":
                _handle_add_task(project)
                save_state(project, state_path)
            elif choice == "4":
                _handle_assign_task(project)
                save_state(project, state_path)
            elif choice == "5":
                _handle_change_status(project)
                save_state(project, state_path)
            elif choice == "6":
                _handle_change_deadline(project)
                save_state(project, state_path)
            elif choice == "7":
                _handle_filter_by_status(project)
            elif choice == "8":
                _handle_show_notifications(project)
            elif choice == "9":
                save_state(project, state_path)
                print(f"Стан проєкту збережено у '{state_path}'.")
            elif choice == "0":
                save_state(project, state_path)
                print(f"Стан збережено у '{state_path}'. До зустрічі!")
                break
            else:
                print("Невідома команда. Введіть цифру від 0 до 9.")
        except TaskManagerError as err:
            print(f"\n[Помилка] {err}")
        except NotImplementedError:
            print(
                "\n[Увага] Цей метод доменного класу ще не реалізовано у Напрямі 1 "
                "(NotImplementedError)."
            )
        except (KeyboardInterrupt, EOFError):
            print("\nПереривання роботи. Спроба зберегти стан...")
            try:
                save_state(project, state_path)
                print(f"Стан збережено у '{state_path}'.")
            except TaskManagerError as err:
                print(f"Не вдалося зберегти стан: {err}")
            break


if __name__ == "__main__":
    main()
