# Контракти доменного шару

Це угода між трьома напрямами. Тут описано **все, на що можна спиратися** в
`task_manager.domain` і `task_manager.exceptions`. Чого тут немає (атрибути з `_`,
методи `_attach_task` / `_detach_task`), те вважається внутрішнім, і його
можна змінювати без попередження.

> **Змінюєш щось у цьому файлі — спершу пишеш у чат, потім пушиш.** Див. CONTRIBUTING.md.

Імпорт:

```python
from task_manager.domain import Task, Project, TeamMember, Status, Priority, Notifiable
from task_manager.exceptions import (
    TaskManagerError, ValidationError, TaskNotFoundError, MemberNotFoundError,
    InvalidStatusTransitionError, DeadlineInPastError, StorageError,
)
```

---

## 1. Загальні домовленості

| Що | Домовленість |
|---|---|
| Ідентифікатори | У кожної сутності є `id: str` (uuid4). Генерується автоматично, але можна передати в конструктор (`id=...`) — так `from_dict` відновлює обʼєкти. Після створення `id` не змінюється. |
| Час | Усі `datetime` **naive, локальний час** (без `tzinfo`). Порівнювати aware і naive в Python не можна, тому не змішуємо. «Зараз» = `datetime.now()`. |
| Enum | `Status` і `Priority` — `Enum` з рядковими значеннями. У JSON: `status.value` → `"IN_PROGRESS"`, назад: `Status("IN_PROGRESS")`. |
| Колекції | `project.tasks`, `project.members`, `member.assigned_tasks` повертають **tuple-копію**. Змінювати склад можна тільки методами (`add_task`, `assign_task`…). |
| Конструктор vs методи | Конструктор приймає будь-який коректний за типами стан (статус `DONE`, дедлайн у минулому), бо через нього відновлює обʼєкти `from_dict`. Бізнес-правила діють на **операціях зміни**: `change_status`, `set_deadline`, `assign_to` / `assign_task`. |
| Звʼязок Task ↔ TeamMember | Двосторонній: `task.assignee` і `member.assigned_tasks`. Встановлюється **тільки** через `Project.assign_task()` (або низькорівнево `Task.assign_to()`), що оновлює обидві сторони. У конструктори виконавця не передають. |
| Рівність | Обʼєкти порівнюються за ідентичністю (`==` за замовчуванням). Для round-trip тестів порівнюйте результати `to_dict()`. |
| Помилки | Домен кидає тільки нащадків `TaskManagerError`. Неправильний тип поля (рядок замість `Priority`, порожня назва) → `ValidationError`. |
| Чистота домену | `domain/` не імпортує `json`, `pandas`, `streamlit`, `storage/`, `analytics/`, не викликає `print` / `input`. |

---

## 2. Перелічення (`domain/enums.py`)

```python
class Status(Enum):   TODO, IN_PROGRESS, REVIEW, DONE, CANCELLED
class Priority(Enum): LOW, MEDIUM, HIGH, CRITICAL
```

`.value` дорівнює імені (`Status.IN_PROGRESS.value == "IN_PROGRESS"`).

| Властивість | Тип | Опис |
|---|---|---|
| `Status.label`, `Priority.label` | `str` | Назва українською для CLI/дашборду («У роботі», «Критичний»). |
| `Status.is_final` | `bool` | `True` для `DONE` і `CANCELLED`. |

Порядок оголошення членів `Priority` — від найнижчого до найвищого; для сортування
в pandas: `pd.Categorical(..., categories=[p.value for p in Priority], ordered=True)`.

### Переходи статусів — `Task.ALLOWED_TRANSITIONS`

Словник `{Status: frozenset[Status]}` (тільки для читання):

| З \ В | TODO | IN_PROGRESS | REVIEW | DONE | CANCELLED |
|---|:-:|:-:|:-:|:-:|:-:|
| **TODO** | – | ✅ | – | – | ✅ |
| **IN_PROGRESS** | – | – | ✅ | – | ✅ |
| **REVIEW** | – | ✅ (на доопрацювання) | – | ✅ | ✅ |
| **DONE** | – | – | – | – | – |
| **CANCELLED** | – | – | – | – | – |

Усе, що не позначено ✅ (зокрема перехід у той самий статус), кидає
`InvalidStatusTransitionError`. Тести краще писати проти **цієї таблиці**, захардкодженої
в тесті, а не проти `ALLOWED_TRANSITIONS`, бо інакше тест перевіряє код сам із собою.

---

## 3. `Notifiable` (`domain/notifiable.py`)

```python
class Notifiable(ABC):
    @abstractmethod
    def get_notification_message(self) -> str: ...
```

Тільки **формує текст**, нічого не відправляє. `Notifiable()` напряму створити не можна
(`TypeError`). `Task`, `Project`, `TeamMember` успадковують і перевизначають:

| Клас | Про що повідомлення |
|---|---|
| `Task` | Про останню зміну статусу («…змінило статус: IN_PROGRESS → REVIEW») або про поточний статус, якщо змін ще не було. |
| `Project` | Про дедлайн: скільки днів лишилось / що минув / що не встановлено, плюс відсоток виконання. |
| `TeamMember` | Про останнє призначене завдання й кількість активних. |

Код, якому потрібні сповіщення, працює з будь-якою сутністю однаково:

```python
for item in [project, *project.tasks, *project.members]:
    print(item.get_notification_message())
```

---

## 4. `Task` (`domain/task.py`)

```python
Task(
    title: str,
    description: str = "",
    priority: Priority = Priority.MEDIUM,
    deadline: datetime | None = None,
    *,
    status: Status = Status.TODO,
    created_at: datetime | None = None,   # None → datetime.now()
    completed_at: datetime | None = None,
    id: str | None = None,                # None → uuid4
)
```

### Атрибути

| Атрибут | Тип | Доступ | Як змінюється |
|---|---|---|---|
| `id` | `str` | читання | ніяк |
| `title` | `str` | читання/запис | `task.title = "..."`; порожній → `ValidationError` |
| `description` | `str` | читання/запис | `task.description = "..."` |
| `priority` | `Priority` | читання/запис | `task.priority = Priority.HIGH`; не `Priority` → `ValidationError` |
| `status` | `Status` | читання | тільки `change_status()` |
| `assignee` | `TeamMember \| None` | читання | тільки `assign_to()` / `Project.assign_task()` |
| `deadline` | `datetime \| None` | читання | тільки `set_deadline()` |
| `created_at` | `datetime` | читання | ніяк |
| `completed_at` | `datetime \| None` | читання | ставиться автоматично при переході в `DONE` |
| `ALLOWED_TRANSITIONS` | `Mapping[Status, frozenset[Status]]` | читання (атрибут класу) | ніяк |

### Методи

| Сигнатура | Що робить | Винятки |
|---|---|---|
| `change_status(new_status: Status) -> None` | Перехід за таблицею; при `DONE` ставить `completed_at = now`. Сюди вішається `@log_status_change`. | `InvalidStatusTransitionError` |
| `allowed_transitions() -> frozenset[Status]` | Куди можна перейти з поточного статусу (для меню CLI). | — |
| `assign_to(member: TeamMember \| None) -> None` | Призначає / знімає виконавця, оновлює обидві сторони. **Не** перевіряє, чи учасник у проєкті — у CLI використовуйте `Project.assign_task`. | — |
| `set_deadline(deadline: datetime \| None, *, now: datetime \| None = None) -> None` | Новий дедлайн (`None` — прибрати). | `DeadlineInPastError` |
| `is_overdue(now: datetime \| None = None) -> bool` | `True`, якщо `deadline < now` і статус не `DONE`/`CANCELLED`. | — |
| `get_notification_message() -> str` | Див. розділ 3. | — |

Параметр `now` є, щоб тести не залежали від поточного часу.

---

## 5. `TeamMember` (`domain/team_member.py`)

```python
TeamMember(name: str, email: str, role: str = "", *, id: str | None = None)
```

| Атрибут | Тип | Доступ | Примітка |
|---|---|---|---|
| `id` | `str` | читання | |
| `name` | `str` | читання/запис | порожнє → `ValidationError` |
| `email` | `str` | читання/запис | без `@` → `ValidationError` |
| `role` | `str` | читання/запис | довільний текст: `"Developer"`, `"QA"`… |
| `assigned_tasks` | `tuple[Task, ...]` | читання | у порядку призначення; змінюється тільки через призначення завдання |

| Сигнатура | Що робить |
|---|---|
| `active_tasks() -> list[Task]` | Призначені завдання не в `DONE` / `CANCELLED`. |
| `get_notification_message() -> str` | Див. розділ 3. |

---

## 6. `Project` (`domain/project.py`)

```python
Project(name: str, *, deadline: datetime | None = None, id: str | None = None)
```

| Атрибут | Тип | Доступ | Примітка |
|---|---|---|---|
| `id` | `str` | читання | |
| `name` | `str` | читання/запис | порожнє → `ValidationError` |
| `deadline` | `datetime \| None` | читання | змінюється через `set_deadline()` |
| `tasks` | `tuple[Task, ...]` | читання | у порядку додавання |
| `members` | `tuple[TeamMember, ...]` | читання | у порядку додавання |

| Сигнатура | Що робить | Винятки |
|---|---|---|
| `add_task(task: Task) -> None` | Додає завдання. | `ValidationError` (дубль id), `MemberNotFoundError` (виконавець не з проєкту) |
| `add_member(member: TeamMember) -> None` | Додає учасника. | `ValidationError` (дубль id) |
| `get_task(task_id: str) -> Task` | Пошук за id. | `TaskNotFoundError` |
| `get_member(member_id: str) -> TeamMember` | Пошук за id. | `MemberNotFoundError` |
| `assign_task(task_id: str, member_id: str) -> None` | Знаходить обидва обʼєкти й повʼязує їх (обидві сторони). Повторне призначення переносить завдання від старого виконавця. | `TaskNotFoundError`, `MemberNotFoundError` |
| `unassign_task(task_id: str) -> None` | Знімає виконавця. | `TaskNotFoundError` |
| `get_tasks_by_status(status: Status) -> list[Task]` | Фільтр за статусом. | — |
| `completion_rate() -> float` | `DONE / (усі − CANCELLED)`, від `0.0` до `1.0`; порожній проєкт → `0.0`. | — |
| `set_deadline(deadline: datetime \| None, *, now: datetime \| None = None) -> None` | Новий дедлайн проєкту. | `DeadlineInPastError` |
| `days_until_deadline(now: datetime \| None = None) -> int \| None` | Календарні дні до дедлайну: `0` — сьогодні, `<0` — минув, `None` — не встановлено. | — |
| `get_notification_message() -> str` | Див. розділ 3. | — |

---

## 7. Винятки (`task_manager/exceptions.py`)

```
TaskManagerError
├── ValidationError(field, message)
├── TaskNotFoundError(task_id, project_name=None)
├── MemberNotFoundError(member_id, project_name=None)
├── InvalidStatusTransitionError(task_id, current, target, *, task_title=None, allowed=())
├── DeadlineInPastError(deadline, entity_name=None)
└── StorageError(path, reason)
```

Кожен виняток зберігає аргументи як атрибути з тими самими іменами (`err.task_id`,
`err.current`, `err.path`…) і формує зрозуміле повідомлення в `str(err)`, тож CLI може
просто показати `print(f"Помилка: {err}")`.

`StorageError` кидає Напрям 2. Будь-яку помилку розбору файлу загортати так:
`raise StorageError(path, "некоректний JSON") from exc`.

---

## 8. Формат `to_dict()` (для `storage/serializer.py`, Напрям 2)

Серіалізація живе **поза доменом** — у `storage/serializer.py`, як вільні функції
(рекомендовані назви: `task_to_dict`, `task_from_dict`, `member_to_dict`, `member_from_dict`,
`project_to_dict`, `project_from_dict`). Усе, що для цього потрібно, доступне через
публічні атрибути й конструктори вище — до приватних полів лізти не треба.

**Посилання між обʼєктами — тільки за id**, ніколи вкладеним обʼєктом (інакше цикл
Task → TeamMember → Task → … і `RecursionError`).

### Task

```json
{
  "id": "3f1c2a9e-8b7d-4c1e-9f0a-2d4b6e8a1c3f",
  "title": "Сторінка логіну",
  "description": "Форма входу з валідацією",
  "status": "IN_PROGRESS",
  "priority": "HIGH",
  "assignee_id": "a7e4b1c2-5d6f-4a8b-9c0d-1e2f3a4b5c6d",
  "deadline": "2026-11-01T18:00:00",
  "created_at": "2026-10-20T10:15:00",
  "completed_at": null
}
```

| Ключ | Звідки | Тип у JSON |
|---|---|---|
| `id` | `task.id` | string |
| `title`, `description` | | string |
| `status` | `task.status.value` | string |
| `priority` | `task.priority.value` | string |
| `assignee_id` | `task.assignee.id` або `null` | string \| null |
| `deadline`, `completed_at` | `.isoformat()` або `null` | string \| null |
| `created_at` | `.isoformat()` | string |

### TeamMember

```json
{
  "id": "a7e4b1c2-5d6f-4a8b-9c0d-1e2f3a4b5c6d",
  "name": "Олена",
  "email": "olena@example.com",
  "role": "Developer",
  "task_ids": ["3f1c2a9e-8b7d-4c1e-9f0a-2d4b6e8a1c3f"]
}
```

`task_ids` — id з `member.assigned_tasks` **у тому ж порядку**.

### Project

```json
{
  "id": "c0ffee00-1234-4abc-8def-001122334455",
  "name": "Курсова: таск-менеджер",
  "deadline": "2026-12-15T23:59:00",
  "members": [ { "...": "словники TeamMember" } ],
  "tasks":   [ { "...": "словники Task" } ]
}
```

### Файл `data/state.json`

```json
{
  "schema_version": 1,
  "project": { "...": "словник Project" }
}
```

`schema_version` дозволить колись змінити формат і розпізнати старі файли.

### Відновлення (двопрохідне)

```python
project = Project(d["name"], deadline=..., id=d["id"])
# Прохід 1: обʼєкти без звʼязків
for m in d["members"]:
    project.add_member(TeamMember(m["name"], m["email"], m["role"], id=m["id"]))
for t in d["tasks"]:
    project.add_task(Task(t["title"], t["description"], Priority(t["priority"]), deadline,
                          status=Status(t["status"]), created_at=..., completed_at=..., id=t["id"]))
# Прохід 2: звʼязки — через публічне API, яке оновлює обидві сторони
for m in d["members"]:
    for task_id in m["task_ids"]:
        project.assign_task(task_id, m["id"])
# Перевірка узгодженості: assignee_id кожного Task має збігатися з тим, що вийшло
```

Будь-який `KeyError` / `ValueError` / `TypeError` / `TaskManagerError` під час завантаження
загортається в `StorageError`.

Не зберігається: попередній статус завдання (для тексту сповіщення). Після
завантаження `Task.get_notification_message()` покаже поточний статус, а не останню зміну.

---

## 9. Поля для аналітики (Напрям 3)

`tasks_to_dataframe(project)` будується тільки з публічних атрибутів:

| Колонка | Джерело |
|---|---|
| `task_id` | `task.id` |
| `title` | `task.title` |
| `status` | `task.status.value` |
| `priority` | `task.priority.value` |
| `assignee_id` / `assignee_name` | `task.assignee.id` / `.name` або `None` |
| `deadline` | `task.deadline` |
| `created_at` | `task.created_at` |
| `completed_at` | `task.completed_at` (є тільки в `DONE`) |
| `is_overdue` | `task.is_overdue()` |

«Виконано в строк» = `status == DONE` і `deadline` задано і `completed_at <= deadline`.
Час виконання = `completed_at - created_at`.

---

## 10. Декоратор `@log_status_change` (Напрям 3 пише, Напрям 1 застосовує)

Застосовується до `Task.change_status(self, new_status)`. Що декоратор може взяти:
`self.id`, `self.title`, `self.status` **до** виклику (старий статус) і **після** (новий).
Якщо метод кинув `InvalidStatusTransitionError`, декоратор має прокинути виняток далі
(можна залогувати спробу).

Вимоги, щоб не зламати чистоту домену:

- `analytics/decorators.py` використовує тільки стандартну бібліотеку (`functools`, `logging`);
- обовʼязково `functools.wraps`;
- **жодного налаштування handler-ів при імпорті** — модуль бере `logging.getLogger(...)`,
  а запис у `logs/status_changes.log` налаштовується окремою функцією, яку викликає `cli.py`;
- `analytics/__init__.py` не імпортує `stats.py` (інакше імпорт `Task` потягне pandas).

> ⚠️ **Відкрите питання:** імпорт декоратора з `analytics/` у `domain/task.py` формально
> порушує правило «домен не імпортує analytics». Варіанти:
>
> 1. **Перенести декоратор у нейтральний модуль** `task_manager/decorators.py` (поза
>    `analytics/`, пише його так само Напрям 3). Домен залежить лише від stdlib-утиліти.
>    *Рекомендовано.*
> 2. Лишити в `analytics/decorators.py` і прийняти виняток із правила, дотримуючись
>    вимог вище.
> 3. Не чіпати `task.py`, а обгорнути метод при старті застосунку:
>    `Task.change_status = log_status_change(Task.change_status)` у `cli.py`. Домен чистий,
>    але декоратора не видно в коді класу, і на захисті це виглядає як «магія».
>
> Поки не вирішено, над `change_status` стоїть `# TODO`.
