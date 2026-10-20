"""Напрям 3: Модуль Pandas-аналітики завдань проєкту.

Функції аналітики (згідно з docs/CONTRACTS.md):
1. tasks_to_dataframe(): перетворення завдань у pandas DataFrame за публічними атрибутами.
2. get_member_workload(): аналіз завантаженості учасників команди.
3. get_on_time_completion_stats(): відсоток виконання в строк та дедлайни.
4. get_priority_distribution(): розподіл завдань за пріоритетами.
5. get_project_summary(): зведені показники (KPI).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Sequence

import pandas as pd

from task_manager.domain.enums import Priority, Status

PRIORITY_ORDER = [Priority.LOW.value, Priority.MEDIUM.value, Priority.HIGH.value, Priority.CRITICAL.value]
STATUS_ORDER = [
    Status.TODO.value,
    Status.IN_PROGRESS.value,
    Status.REVIEW.value,
    Status.DONE.value,
    Status.CANCELLED.value,
]


def _extract_attr_or_key(item: Any, attr: str, default: Any = None) -> Any:
    """Універсальний доступ: через атрибут об'єкта або за ключем словника."""
    if isinstance(item, dict):
        return item.get(attr, default)
    return getattr(item, attr, default)


def _to_datetime(val: Any) -> datetime | None:
    """Безпечне приведення до naive datetime (без tzinfo)."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val)
            return dt.replace(tzinfo=None)
        except ValueError:
            return None
    return None


def tasks_to_dataframe(project_or_tasks: Any, members: Sequence[Any] | None = None) -> pd.DataFrame:
    """Формує pandas.DataFrame на основі завдань проєкту (CONTRACTS.md розділ 9)."""
    now = datetime.now()

    if isinstance(project_or_tasks, pd.DataFrame):
        return project_or_tasks.copy()

    raw_tasks: list[Any] = []
    members_map: dict[str, str] = {}

    if hasattr(project_or_tasks, "tasks"):
        raw_tasks = list(project_or_tasks.tasks)
        if hasattr(project_or_tasks, "members"):
            for m in project_or_tasks.members:
                members_map[str(m.id)] = str(m.name)
    elif isinstance(project_or_tasks, dict):
        root = project_or_tasks.get("project", project_or_tasks)
        raw_tasks = list(root.get("tasks", []))
        for m in root.get("members", []):
            m_id = str(m.get("id", ""))
            m_name = str(m.get("name", "Невідомий"))
            if m_id:
                members_map[m_id] = m_name
    elif isinstance(project_or_tasks, Iterable):
        raw_tasks = list(project_or_tasks)

    if members:
        for m in members:
            m_id = str(_extract_attr_or_key(m, "id", ""))
            m_name = str(_extract_attr_or_key(m, "name", "Невідомий"))
            if m_id:
                members_map[m_id] = m_name

    rows: list[dict[str, Any]] = []

    for t in raw_tasks:
        task_id = str(_extract_attr_or_key(t, "id", ""))
        title = str(_extract_attr_or_key(t, "title", "Без назви"))
        desc = str(_extract_attr_or_key(t, "description", ""))

        raw_status = _extract_attr_or_key(t, "status", Status.TODO)
        status_val = raw_status.value if hasattr(raw_status, "value") else str(raw_status)
        try:
            status_label = Status(status_val).label
        except (ValueError, KeyError):
            status_label = status_val

        raw_priority = _extract_attr_or_key(t, "priority", Priority.MEDIUM)
        priority_val = raw_priority.value if hasattr(raw_priority, "value") else str(raw_priority)
        try:
            priority_label = Priority(priority_val).label
        except (ValueError, KeyError):
            priority_label = priority_val

        assignee_obj = _extract_attr_or_key(t, "assignee", None)
        assignee_id = _extract_attr_or_key(t, "assignee_id", None)
        assignee_name = "Не призначено"

        if assignee_obj is not None:
            assignee_id = str(_extract_attr_or_key(assignee_obj, "id", ""))
            assignee_name = str(_extract_attr_or_key(assignee_obj, "name", "Не призначено"))
        elif assignee_id is not None:
            assignee_id = str(assignee_id)
            assignee_name = members_map.get(assignee_id, "Не призначено")

        created_at = _to_datetime(_extract_attr_or_key(t, "created_at", None)) or now
        deadline = _to_datetime(_extract_attr_or_key(t, "deadline", None))
        completed_at = _to_datetime(_extract_attr_or_key(t, "completed_at", None))

        is_overdue = False
        if hasattr(t, "is_overdue"):
            try:
                is_overdue = bool(t.is_overdue(now))
            except NotImplementedError:
                if status_val not in (Status.DONE.value, Status.CANCELLED.value):
                    is_overdue = deadline is not None and deadline < now
        else:
            if status_val not in (Status.DONE.value, Status.CANCELLED.value):
                is_overdue = deadline is not None and deadline < now

        is_on_time: bool | None = None
        if status_val == Status.DONE.value:
            if deadline is not None and completed_at is not None:
                is_on_time = completed_at <= deadline
            elif deadline is None:
                is_on_time = True

        duration_days = None
        if completed_at and created_at:
            duration_days = round((completed_at - created_at).total_seconds() / 86400, 2)

        rows.append(
            {
                "task_id": task_id,
                "title": title,
                "description": desc,
                "status": status_val,
                "status_label": status_label,
                "priority": priority_val,
                "priority_label": priority_label,
                "assignee_id": assignee_id,
                "assignee_name": assignee_name,
                "deadline": deadline,
                "created_at": created_at,
                "completed_at": completed_at,
                "is_overdue": is_overdue,
                "is_on_time": is_on_time,
                "duration_days": duration_days,
            }
        )

    columns = [
        "task_id", "title", "description", "status", "status_label",
        "priority", "priority_label", "assignee_id", "assignee_name",
        "deadline", "created_at", "completed_at", "is_overdue", "is_on_time", "duration_days",
    ]

    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    df["priority"] = pd.Categorical(df["priority"], categories=PRIORITY_ORDER, ordered=True)
    df["status"] = pd.Categorical(df["status"], categories=STATUS_ORDER, ordered=True)
    return df


def get_member_workload(project_or_tasks: Any, members: Sequence[Any] | None = None) -> pd.DataFrame:
    """Pandas-аналіз завантаженості учасників команди."""
    df = tasks_to_dataframe(project_or_tasks, members)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "member_name", "total_tasks", "active_tasks",
                "in_progress", "review", "todo", "done",
                "overdue", "workload_share_pct",
            ]
        )

    active_statuses = [Status.TODO.value, Status.IN_PROGRESS.value, Status.REVIEW.value]
    total_active_project = int(df["status"].isin(active_statuses).sum())

    workload_list: list[dict[str, Any]] = []

    for member_name, group in df.groupby("assignee_name", observed=False):
        total = len(group)
        in_progress = int((group["status"] == Status.IN_PROGRESS.value).sum())
        review = int((group["status"] == Status.REVIEW.value).sum())
        todo = int((group["status"] == Status.TODO.value).sum())
        done = int((group["status"] == Status.DONE.value).sum())
        active = int(group["status"].isin(active_statuses).sum())
        overdue = int((group["is_overdue"] & group["status"].isin(active_statuses)).sum())

        share = round((active / total_active_project * 100), 1) if total_active_project > 0 else 0.0

        workload_list.append(
            {
                "member_name": str(member_name),
                "total_tasks": total,
                "active_tasks": active,
                "in_progress": in_progress,
                "review": review,
                "todo": todo,
                "done": done,
                "overdue": overdue,
                "workload_share_pct": share,
            }
        )

    res_df = pd.DataFrame(workload_list)
    return res_df.sort_values(by=["active_tasks", "total_tasks"], ascending=[False, False]).reset_index(drop=True)


def get_on_time_completion_stats(project_or_tasks: Any) -> dict[str, Any]:
    """Аналіз відсотка виконання завдань у строк та стану дедлайнів."""
    df = tasks_to_dataframe(project_or_tasks)

    if df.empty:
        return {
            "total_completed": 0, "completed_with_deadline": 0,
            "completed_on_time": 0, "completed_late": 0,
            "on_time_rate_pct": 100.0, "open_overdue": 0,
            "open_on_track": 0, "overdue_tasks_df": pd.DataFrame(),
        }

    now = datetime.now()

    done_mask = df["status"] == Status.DONE.value
    done_df = df[done_mask]
    total_completed = len(done_df)

    completed_with_deadline = int(done_df["deadline"].notna().sum())
    completed_on_time = int((done_df["is_on_time"] == True).sum())  # noqa: E712
    completed_late = int((done_df["is_on_time"] == False).sum())  # noqa: E712

    if completed_with_deadline > 0:
        on_time_rate = round((completed_on_time / completed_with_deadline) * 100, 1)
    else:
        on_time_rate = 100.0 if total_completed > 0 else 0.0

    open_statuses = [Status.TODO.value, Status.IN_PROGRESS.value, Status.REVIEW.value]
    open_df = df[df["status"].isin(open_statuses)]

    open_overdue_mask = open_df["is_overdue"] == True  # noqa: E712
    open_overdue = int(open_overdue_mask.sum())
    open_on_track = len(open_df) - open_overdue

    overdue_rows = open_df[open_overdue_mask].copy()
    if not overdue_rows.empty:
        overdue_rows["days_overdue"] = overdue_rows["deadline"].apply(
            lambda d: max(1, (now - d).days) if pd.notna(d) else 0
        )
        overdue_display = overdue_rows[
            ["task_id", "title", "assignee_name", "priority_label", "status_label", "deadline", "days_overdue"]
        ].sort_values(by="days_overdue", ascending=False)
    else:
        overdue_display = pd.DataFrame(
            columns=["task_id", "title", "assignee_name", "priority_label", "status_label", "deadline", "days_overdue"]
        )

    return {
        "total_completed": total_completed,
        "completed_with_deadline": completed_with_deadline,
        "completed_on_time": completed_on_time,
        "completed_late": completed_late,
        "on_time_rate_pct": on_time_rate,
        "open_overdue": open_overdue,
        "open_on_track": open_on_track,
        "overdue_tasks_df": overdue_display,
    }


def get_priority_distribution(project_or_tasks: Any) -> pd.DataFrame:
    """Аналіз розподілу завдань за пріоритетами."""
    df = tasks_to_dataframe(project_or_tasks)

    if df.empty:
        return pd.DataFrame(columns=["priority", "label", "count", "percentage"])

    total = len(df)
    counts = df["priority"].value_counts(sort=False)

    records: list[dict[str, Any]] = []
    for p in Priority:
        cnt = int(counts.get(p.value, 0))
        pct = round((cnt / total * 100), 1) if total > 0 else 0.0
        records.append({"priority": p.value, "label": p.label, "count": cnt, "percentage": pct})

    return pd.DataFrame(records)


def get_priority_status_matrix(project_or_tasks: Any) -> pd.DataFrame:
    """Крос-таблиця розподілу завдань: Пріоритет x Статус."""
    df = tasks_to_dataframe(project_or_tasks)
    if df.empty:
        return pd.DataFrame()

    crosstab = pd.crosstab(df["priority"], df["status"], dropna=False)
    status_label_map = {s.value: s.label for s in Status}
    priority_label_map = {p.value: p.label for p in Priority}
    crosstab.rename(columns=status_label_map, index=priority_label_map, inplace=True)
    return crosstab


def get_project_summary(project_or_tasks: Any, members: Sequence[Any] | None = None) -> dict[str, Any]:
    """Зведені KPI показники проєкту."""
    df = tasks_to_dataframe(project_or_tasks, members)
    total_tasks = len(df)

    if total_tasks == 0:
        return {
            "total_tasks": 0, "completed_tasks": 0, "completion_rate_pct": 0.0,
            "active_tasks": 0, "overdue_tasks": 0, "total_members": 0, "on_time_rate_pct": 100.0,
        }

    completed_tasks = int((df["status"] == Status.DONE.value).sum())
    cancelled_tasks = int((df["status"] == Status.CANCELLED.value).sum())
    active_tasks = total_tasks - completed_tasks - cancelled_tasks
    overdue_tasks = int((df["is_overdue"] & (df["status"] != Status.DONE.value) & (df["status"] != Status.CANCELLED.value)).sum())

    valid_tasks = total_tasks - cancelled_tasks
    comp_rate = round((completed_tasks / valid_tasks * 100), 1) if valid_tasks > 0 else 0.0

    on_time_stats = get_on_time_completion_stats(df)
    unique_assignees = df["assignee_id"].dropna().nunique()

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate_pct": comp_rate,
        "active_tasks": active_tasks,
        "overdue_tasks": overdue_tasks,
        "total_members": unique_assignees,
        "on_time_rate_pct": on_time_stats["on_time_rate_pct"],
    }
