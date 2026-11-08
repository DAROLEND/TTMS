"""Напрям 3: Дашборд аналітики на Streamlit.

Запуск: python -m streamlit run task_manager/dashboard.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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


def load_project_data() -> tuple[dict[str, Any] | Any, str]:
    """Безпечне завантаження даних (з файлу або демо)."""
    if "custom_project_data" in st.session_state and st.session_state["custom_project_data"]:
        return st.session_state["custom_project_data"], "Завантажений користувачем JSON"

    if STATE_FILE.is_file():
        try:
            try:
                from task_manager.storage.serializer import load_state
                project = load_state(str(STATE_FILE))
                return project, f"Сховище ({STATE_FILE})"
            except Exception:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data, f"Файл JSON ({STATE_FILE})"
        except Exception as e:
            st.sidebar.error(f"Помилка читання: {e}")

    if "demo_data" not in st.session_state:
        st.session_state["demo_data"] = _generate_demo_data()
    return st.session_state["demo_data"], "Демонстраційні дані (очікує створення data/state.json)"


def main() -> None:
    st.set_page_config(
        page_title="TTMS | Панель аналітики",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📊 TTMS: Аналітична панель управління проєктом")
    st.markdown(
        "**Напрям 3: Аналітика** — Pandas-аналіз завантаженості команди, дедлайнів, "
        "своєчасності виконання та розподілу за пріоритетами."
    )

    raw_data, source_desc = load_project_data()
    df_all = tasks_to_dataframe(raw_data)

    proj_name = "TTMS Project"
    if hasattr(raw_data, "name"):
        proj_name = raw_data.name
    elif isinstance(raw_data, dict):
        proj_dict = raw_data.get("project", raw_data)
        proj_name = proj_dict.get("name", proj_name)

    with st.sidebar:
        st.header("⚙️ Керування даними")
        st.info(f"**Джерело даних:** {source_desc}")

        uploaded = st.file_uploader("Завантажити інший `state.json`", type=["json"])
        if uploaded is not None:
            try:
                st.session_state["custom_project_data"] = json.load(uploaded)
                st.success("Файл завантажено!")
                st.rerun()
            except Exception as e:
                st.error(f"Некоректний JSON: {e}")

        if st.button("🔄 Скинути до демо"):
            st.session_state["custom_project_data"] = None
            st.session_state["demo_data"] = _generate_demo_data()
            st.rerun()

        st.markdown("---")
        st.header("🔍 Фільтри")

        all_statuses = [s.value for s in Status]
        selected_statuses = st.multiselect(
            "Статус:", options=all_statuses, default=all_statuses,
            format_func=lambda x: f"{x} ({Status(x).label})",
        )

        all_priorities = [p.value for p in Priority]
        selected_priorities = st.multiselect(
            "Пріоритет:", options=all_priorities, default=all_priorities,
            format_func=lambda x: f"{x} ({Priority(x).label})",
        )

        assignees = sorted(df_all["assignee_name"].dropna().unique().tolist())
        selected_assignees = st.multiselect("Виконавець:", options=assignees, default=assignees)
        search = st.text_input("Пошук за назвою:", "").strip()

    df_filtered = df_all.copy()
    if not df_filtered.empty:
        if selected_statuses:
            df_filtered = df_filtered[df_filtered["status"].isin(selected_statuses)]
        if selected_priorities:
            df_filtered = df_filtered[df_filtered["priority"].isin(selected_priorities)]
        if selected_assignees:
            df_filtered = df_filtered[df_filtered["assignee_name"].isin(selected_assignees)]
        if search:
            df_filtered = df_filtered[df_filtered["title"].str.contains(search, case=False, na=False)]

    st.subheader(f"Проєкт: {proj_name}")

    summary = get_project_summary(df_all)
    on_time = get_on_time_completion_stats(df_all)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📌 Всього завдань", summary["total_tasks"])
    c2.metric("✅ Виконано", f"{summary['completed_tasks']} ({summary['completion_rate_pct']}%)")
    c3.metric("⏱️ У строк", f"{on_time['on_time_rate_pct']}%",
              delta=f"{on_time['completed_on_time']} з {on_time['completed_with_deadline']}")
    c4.metric("⚠️ Прострочено", on_time["open_overdue"],
              delta=f"-{on_time['open_overdue']}" if on_time["open_overdue"] > 0 else "0",
              delta_color="inverse")
    c5.metric("👥 Виконавців", summary["total_members"])

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 Завантаженість команди", "⏱️ Дедлайни та своєчасність",
        "🎯 Розподіл за пріоритетами", "📋 Реєстр завдань", "📜 Журнал аудиту (Логи)",
    ])

    with tab1:
        st.subheader("👥 Завантаженість учасників команди")
        workload = get_member_workload(df_filtered)
        if workload.empty:
            st.warning("Немає завдань за фільтрами.")
        else:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("##### Завдання за виконавцями")
                st.bar_chart(workload.set_index("member_name")[["in_progress", "review", "todo", "done"]])
            with col2:
                st.markdown("##### Частка завантаження (%)")
                share = workload[workload["member_name"] != "Не призначено"].set_index("member_name")["workload_share_pct"]
                if not share.empty and share.sum() > 0:
                    st.bar_chart(share)

            st.dataframe(workload.rename(columns={
                "member_name": "Виконавець", "total_tasks": "Всього",
                "active_tasks": "Активних", "in_progress": "У роботі",
                "review": "На перевірці", "todo": "До виконання",
                "done": "Виконано", "overdue": "Прострочено",
                "workload_share_pct": "Частка (%)",
            }), use_container_width=True)

    with tab2:
        st.subheader("⏱️ Своєчасність виконання та дедлайни")
        col1, col2 = st.columns([1, 2])
        with col1:
            chart_df = pd.DataFrame(
                {"Категорія": ["Вчасно", "Із запізненням"],
                 "Кількість": [on_time["completed_on_time"], on_time["completed_late"]]}
            ).set_index("Категорія")
            st.bar_chart(chart_df)
            st.write(f"- Відсоток виконання в строк: **{on_time['on_time_rate_pct']}%**")
        with col2:
            st.markdown("##### ⚠️ Прострочені завдання")
            overdue_df = on_time["overdue_tasks_df"]
            if overdue_df.empty:
                st.success("🎉 Усі завдання у графіку!")
            else:
                st.error(f"Виявлено {len(overdue_df)} прострочених:")
                st.dataframe(overdue_df.rename(columns={
                    "task_id": "ID", "title": "Назва", "assignee_name": "Виконавець",
                    "priority_label": "Пріоритет", "status_label": "Статус",
                    "deadline": "Дедлайн", "days_overdue": "Днів прострочено",
                }), use_container_width=True)

    with tab3:
        st.subheader("🎯 Розподіл за пріоритетами")
        priorities = get_priority_distribution(df_filtered)
        col1, col2 = st.columns([1, 1])
        with col1:
            if not priorities.empty:
                st.bar_chart(priorities.set_index("label")["count"])
        with col2:
            if not priorities.empty:
                st.dataframe(priorities.rename(columns={
                    "priority": "Код", "label": "Пріоритет",
                    "count": "Кількість", "percentage": "%",
                }), use_container_width=True)
        st.markdown("##### Крос-таблиця: Пріоритет × Статус")
        st.dataframe(get_priority_status_matrix(df_filtered), use_container_width=True)

    with tab4:
        st.subheader("📋 Повний список завдань")
        if df_filtered.empty:
            st.info("Немає записів.")
        else:
            cols = ["title", "status_label", "priority_label", "assignee_name", "deadline", "is_overdue", "completed_at"]
            st.dataframe(df_filtered[cols].rename(columns={
                "title": "Назва", "status_label": "Статус", "priority_label": "Пріоритет",
                "assignee_name": "Виконавець", "deadline": "Дедлайн",
                "is_overdue": "Прострочено", "completed_at": "Завершено",
            }), use_container_width=True)
            st.download_button("📥 Експорт у CSV",
                               data=df_filtered.to_csv(index=False).encode("utf-8"),
                               file_name="tasks_report.csv", mime="text/csv")

    with tab5:
        st.subheader("📜 Журнал аудиту змін статусів")
        logs = read_status_logs(LOG_FILE)
        if not logs:
            st.info("Журнал порожній або logs/status_changes.log ще не створено.")
        else:
            st.dataframe(pd.DataFrame(logs).rename(columns={
                "timestamp": "Час", "level": "Рівень",
                "task_id": "ID завдання", "message": "Подія",
            }), use_container_width=True)


if __name__ == "__main__":
    main()
