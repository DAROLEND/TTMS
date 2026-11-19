"""Напрям 3: Дашборд аналітики на Streamlit.

Запуск: python -m streamlit run task_manager/dashboard.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from task_manager.analytics.decorators import read_status_logs
from task_manager.analytics.stats import (
    get_member_workload,
    get_on_time_completion_stats,
    get_priority_distribution,
    get_priority_status_matrix,
    get_project_summary,
    tasks_to_dataframe,
)
from task_manager.domain.enums import Priority, Status

STATE_FILE = Path("data/state.json")
LOG_FILE = Path("logs/status_changes.log")

# Кольори статусів однакові на всіх графіках.
STATUS_COLORS = {
    Status.TODO: "#8C96A3",
    Status.IN_PROGRESS: "#4C78A8",
    Status.REVIEW: "#E0A33A",
    Status.DONE: "#54A24B",
    Status.CANCELLED: "#B9B9B9",
}
ACCENT = "#4C78A8"
DATE_FORMAT = "DD.MM.YYYY HH:mm"


def _generate_demo_data() -> dict[str, Any]:
    """Створює реалістичні дані для демонстрації роботи аналітики."""
    now = datetime.now()
    members = [
        {"id": "m1", "name": "Олександр Шевченко", "email": "o.shev@uni.edu", "role": "Backend"},
        {"id": "m2", "name": "Марія Коваль", "email": "m.koval@uni.edu", "role": "Frontend"},
        {"id": "m3", "name": "Дмитро Бондар", "email": "d.bond@uni.edu", "role": "Data Analyst"},
        {"id": "m4", "name": "Анна Ткаченко", "email": "a.tkach@uni.edu", "role": "QA"},
    ]

    tasks = [
        {
            "id": "t1", "title": "Розробити архітектуру доменного шару",
            "description": "Створити класи Task, Project, TeamMember",
            "status": Status.DONE.value, "priority": Priority.CRITICAL.value,
            "assignee_id": "m1",
            "created_at": (now - timedelta(days=10)).isoformat(),
            "deadline": (now - timedelta(days=5)).isoformat(),
            "completed_at": (now - timedelta(days=6)).isoformat(),
        },
        {
            "id": "t2", "title": "Налаштувати JSON-серіалізатор",
            "description": "Збереження та відновлення стану",
            "status": Status.DONE.value, "priority": Priority.HIGH.value,
            "assignee_id": "m2",
            "created_at": (now - timedelta(days=8)).isoformat(),
            "deadline": (now - timedelta(days=3)).isoformat(),
            "completed_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "id": "t3", "title": "Реалізувати декоратор @log_status_change",
            "description": "Логування переходів у logs/status_changes.log",
            "status": Status.DONE.value, "priority": Priority.HIGH.value,
            "assignee_id": "m3",
            "created_at": (now - timedelta(days=6)).isoformat(),
            "deadline": (now - timedelta(days=2)).isoformat(),
            "completed_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "id": "t4", "title": "Розробити дашборд на Streamlit",
            "description": "Візуалізація метрик команди",
            "status": Status.IN_PROGRESS.value, "priority": Priority.CRITICAL.value,
            "assignee_id": "m3",
            "created_at": (now - timedelta(days=4)).isoformat(),
            "deadline": (now + timedelta(days=2)).isoformat(),
            "completed_at": None,
        },
        {
            "id": "t5", "title": "Написати модульні тести",
            "description": "Покрити переходи статусів і дедлайни",
            "status": Status.IN_PROGRESS.value, "priority": Priority.MEDIUM.value,
            "assignee_id": "m4",
            "created_at": (now - timedelta(days=5)).isoformat(),
            "deadline": (now - timedelta(days=1)).isoformat(),
            "completed_at": None,
        },
        {
            "id": "t6", "title": "Створити консольний інтерфейс CLI",
            "description": "Меню управління завданнями",
            "status": Status.TODO.value, "priority": Priority.HIGH.value,
            "assignee_id": "m1",
            "created_at": (now - timedelta(days=3)).isoformat(),
            "deadline": (now + timedelta(days=4)).isoformat(),
            "completed_at": None,
        },
    ]

    return {
        "schema_version": 1,
        "project": {
            "id": "demo-01",
            "name": "TTMS: Система управління завданнями (Демо)",
            "deadline": (now + timedelta(days=14)).isoformat(),
            "members": members,
            "tasks": tasks,
        },
    }


SOURCE_STATE = "Мій проєкт"
SOURCE_DEMO = "Демодані"


def load_project_data() -> tuple[dict[str, Any] | Any, str]:
    """Дані для дашборду: завантажений файл, data/state.json або демо."""
    if st.session_state.get("custom_project_data"):
        return st.session_state["custom_project_data"], "завантажений файл"

    # None — користувач зняв вибір; тоді показуємо свій проєкт.
    use_state = (st.session_state.get("data_source") or SOURCE_STATE) == SOURCE_STATE
    if STATE_FILE.is_file() and use_state:
        try:
            try:
                from task_manager.storage.serializer import load_state
                return load_state(str(STATE_FILE)), str(STATE_FILE)
            except Exception:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f), f"{STATE_FILE} (як JSON)"
        except Exception as e:
            st.sidebar.error(f"Помилка читання: {e}")

    if "demo_data" not in st.session_state:
        st.session_state["demo_data"] = _generate_demo_data()
    return st.session_state["demo_data"], "демодані"


def _on_upload() -> None:
    """Викликається, коли файл вибрали або прибрали з поля завантаження."""
    file = st.session_state.get("uploaded_json")
    st.session_state["upload_error"] = None
    st.session_state["custom_project_data"] = None
    if file is not None:
        try:
            st.session_state["custom_project_data"] = json.load(file)
        except Exception as e:
            st.session_state["upload_error"] = str(e)


# Висота одного рядка горизонтальної діаграми, щоб графік не стискався.
ROW_STEP = alt.Step(40)


def _workload_chart(workload: pd.DataFrame) -> alt.Chart:
    """Горизонтальні стовпці: скільки завдань кожного статусу в учасника."""
    columns = {
        "todo": Status.TODO,
        "in_progress": Status.IN_PROGRESS,
        "review": Status.REVIEW,
        "done": Status.DONE,
    }
    names = workload["member_name"].tolist()
    long = workload.melt(
        id_vars="member_name", value_vars=list(columns), var_name="key", value_name="count"
    )
    long["status"] = long["key"].map(lambda k: columns[k].label)
    long["order"] = long["key"].map(list(columns).index)
    long = long[long["count"] > 0]

    labels = [s.label for s in columns.values()]
    colors = [STATUS_COLORS[s] for s in columns.values()]
    return (
        alt.Chart(long)
        .mark_bar()
        .encode(
            y=alt.Y("member_name:N", title=None, sort=names, scale=alt.Scale(domain=names),
                    axis=alt.Axis(labelLimit=220)),
            x=alt.X("count:Q", title="Кількість завдань", axis=alt.Axis(tickMinStep=1, format="d")),
            color=alt.Color(
                "status:N",
                title=None,
                scale=alt.Scale(domain=labels, range=colors),
                legend=alt.Legend(orient="top"),
            ),
            order=alt.Order("order:Q"),
            tooltip=[
                alt.Tooltip("member_name:N", title="Виконавець"),
                alt.Tooltip("status:N", title="Статус"),
                alt.Tooltip("count:Q", title="Завдань"),
            ],
        )
        .properties(height=ROW_STEP)
    )


def _simple_bar(
    data: pd.DataFrame, label: str, value: str, *, value_title: str, colors: list[str] | None = None
) -> alt.Chart:
    """Горизонтальна діаграма з цілими значеннями; порядок рядків як у data."""
    order = data[label].tolist()
    color = (
        alt.Color(f"{label}:N", scale=alt.Scale(domain=order, range=colors), legend=None)
        if colors
        else alt.value(ACCENT)
    )
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            y=alt.Y(f"{label}:N", title=None, sort=order, axis=alt.Axis(labelLimit=220)),
            x=alt.X(f"{value}:Q", title=value_title, axis=alt.Axis(tickMinStep=1, format="d")),
            color=color,
            tooltip=[alt.Tooltip(f"{label}:N", title=" "), alt.Tooltip(f"{value}:Q", title=value_title)],
        )
        .properties(height=ROW_STEP)
    )


def main() -> None:
    st.set_page_config(page_title="TTMS — аналітика", layout="wide")

    raw_data, source_desc = load_project_data()
    df_all = tasks_to_dataframe(raw_data)

    proj_name = "TTMS Project"
    if hasattr(raw_data, "name"):
        proj_name = raw_data.name
    elif isinstance(raw_data, dict):
        proj_dict = raw_data.get("project", raw_data)
        proj_name = proj_dict.get("name", proj_name)

    with st.sidebar:
        st.subheader("Дані")
        if STATE_FILE.is_file():
            st.segmented_control(
                "Що показувати", [SOURCE_STATE, SOURCE_DEMO], key="data_source",
                default=SOURCE_STATE, width="stretch",
            )
        st.caption(f"Джерело: {source_desc}")

        st.file_uploader(
            "Відкрити інший state.json", type=["json"],
            key="uploaded_json", on_change=_on_upload,
            help="Щоб повернутися назад, приберіть файл хрестиком.",
        )
        if st.session_state.get("upload_error"):
            st.error(f"Некоректний JSON: {st.session_state['upload_error']}")

        st.divider()
        st.subheader("Фільтри")
        st.caption("Якщо нічого не вибрано — показуються всі.")

        selected_statuses = st.pills(
            "Статус", [s.value for s in Status], selection_mode="multi",
            format_func=lambda x: Status(x).label,
        )
        selected_priorities = st.pills(
            "Пріоритет", [p.value for p in Priority], selection_mode="multi",
            format_func=lambda x: Priority(x).label,
        )
        assignees = sorted(df_all["assignee_name"].dropna().unique().tolist()) if not df_all.empty else []
        selected_assignees = st.multiselect("Виконавець", assignees, placeholder="Усі виконавці")
        search = st.text_input("Пошук", "", placeholder="Назва завдання або імʼя").strip()

    df_filtered = df_all.copy()
    if not df_filtered.empty:
        if selected_statuses:
            df_filtered = df_filtered[df_filtered["status"].isin(selected_statuses)]
        if selected_priorities:
            df_filtered = df_filtered[df_filtered["priority"].isin(selected_priorities)]
        if selected_assignees:
            df_filtered = df_filtered[df_filtered["assignee_name"].isin(selected_assignees)]
        if search:
            in_title = df_filtered["title"].str.contains(search, case=False, na=False, regex=False)
            in_name = df_filtered["assignee_name"].astype(str).str.contains(search, case=False, regex=False)
            df_filtered = df_filtered[in_title | in_name]

    st.title("Аналітика проєкту")
    st.caption(proj_name)

    # Картки й вкладки рахуються по відфільтрованих завданнях.
    summary = get_project_summary(df_filtered)
    on_time = get_on_time_completion_stats(df_filtered)
    if len(df_filtered) != len(df_all):
        st.caption(f"Показано {len(df_filtered)} з {len(df_all)} завдань за фільтрами")
    on_time_value = f"{on_time['on_time_rate_pct']}%" if on_time["completed_with_deadline"] else "—"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Усього завдань", summary["total_tasks"], border=True)
    c2.metric("Виконано", f"{summary['completion_rate_pct']}%", border=True,
              help=f"{summary['completed_tasks']} з {summary['total_tasks']} завдань")
    c3.metric("Вчасно", on_time_value, border=True,
              help=f"{on_time['completed_on_time']} з {on_time['completed_with_deadline']} "
                   "виконаних завдань із дедлайном")
    c4.metric("Прострочено", on_time["open_overdue"], border=True,
              help="Активні завдання, у яких минув дедлайн")
    c5.metric("Виконавців", summary["total_members"], border=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Завантаженість", "Дедлайни", "Пріоритети", "Усі завдання", "Журнал змін"]
    )

    with tab1:
        workload = get_member_workload(df_filtered)
        if workload.empty:
            st.info("Немає завдань за вибраними фільтрами.")
        else:
            st.altair_chart(_workload_chart(workload), width="stretch")
            st.dataframe(
                workload.rename(columns={
                    "member_name": "Виконавець", "total_tasks": "Усього",
                    "active_tasks": "Активних", "in_progress": "У роботі",
                    "review": "На перевірці", "todo": "До виконання",
                    "done": "Виконано", "overdue": "Прострочено",
                    "workload_share_pct": "Частка активних, %",
                }),
                hide_index=True, width="stretch",
            )

    with tab2:
        col1, col2 = st.columns([1, 2], gap="large")
        with col1:
            st.markdown("**Виконані завдання**")
            timing = pd.DataFrame({
                "Категорія": ["Вчасно", "Із запізненням"],
                "Кількість": [on_time["completed_on_time"], on_time["completed_late"]],
            })
            st.altair_chart(
                _simple_bar(timing, "Категорія", "Кількість", value_title="Завдань",
                            colors=[STATUS_COLORS[Status.DONE], "#D0605E"]),
                width="stretch",
            )
        with col2:
            st.markdown("**Прострочені активні завдання**")
            overdue_df = on_time["overdue_tasks_df"]
            if overdue_df.empty:
                st.success("Прострочених завдань немає.")
            else:
                st.dataframe(
                    overdue_df.drop(columns=["task_id"]).rename(columns={
                        "title": "Назва", "assignee_name": "Виконавець",
                        "priority_label": "Пріоритет", "status_label": "Статус",
                        "deadline": "Дедлайн", "days_overdue": "Днів прострочено",
                    }),
                    hide_index=True, width="stretch",
                    column_config={"Дедлайн": st.column_config.DatetimeColumn(format=DATE_FORMAT)},
                )

    with tab3:
        priorities = get_priority_distribution(df_filtered)
        if priorities.empty:
            st.info("Немає завдань за вибраними фільтрами.")
        else:
            col1, col2 = st.columns([1, 1], gap="large")
            with col1:
                st.markdown("**Завдань за пріоритетом**")
                st.altair_chart(
                    _simple_bar(priorities, "label", "count", value_title="Завдань"),
                    width="stretch",
                )
            with col2:
                st.markdown("**Пріоритет × статус**")
                matrix = get_priority_status_matrix(df_filtered)
                matrix.index.name = "Пріоритет"
                matrix.columns.name = None
                st.dataframe(matrix, width="stretch")

    with tab4:
        if df_filtered.empty:
            st.info("Немає завдань за вибраними фільтрами.")
        else:
            cols = ["title", "status_label", "priority_label", "assignee_name",
                    "deadline", "is_overdue", "completed_at"]
            st.dataframe(
                df_filtered[cols].rename(columns={
                    "title": "Назва", "status_label": "Статус", "priority_label": "Пріоритет",
                    "assignee_name": "Виконавець", "deadline": "Дедлайн",
                    "is_overdue": "Прострочено", "completed_at": "Завершено",
                }),
                hide_index=True, width="stretch",
                column_config={
                    "Дедлайн": st.column_config.DatetimeColumn(format=DATE_FORMAT),
                    "Завершено": st.column_config.DatetimeColumn(format=DATE_FORMAT),
                    "Прострочено": st.column_config.CheckboxColumn(),
                },
            )
            st.download_button(
                "Експорт у CSV",
                data=df_filtered.to_csv(index=False).encode("utf-8"),
                file_name="tasks_report.csv", mime="text/csv",
            )

    with tab5:
        logs = read_status_logs(LOG_FILE)
        if not logs:
            st.info("Журнал порожній: logs/status_changes.log ще не створено.")
        else:
            st.dataframe(
                pd.DataFrame(logs).rename(columns={
                    "timestamp": "Час", "level": "Рівень",
                    "task_id": "ID завдання", "message": "Подія",
                }),
                hide_index=True, width="stretch",
            )


if __name__ == "__main__":
    main()
