"""Напрям 3: Декоратори аналітики та аудиту.

Декоратор @log_status_change для автоматичного логування зміни статусу завдання.
Вимоги з docs/CONTRACTS.md:
- Використовує тільки стандартну бібліотеку (functools, logging).
- Зберігає метадані функції через @functools.wraps.
- Жодного налаштування handler-ів при імпорті (лише logging.getLogger).
- Запис у logs/status_changes.log налаштовується функцією setup_status_logger().
- При InvalidStatusTransitionError або інших винятках прокидає помилку далі.
"""

from __future__ import annotations

import functools
import logging
import re
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger("task_manager.status_change")

F = TypeVar("F", bound=Callable[..., Any])


def setup_status_logger(
    log_file: str | Path = "logs/status_changes.log",
    level: int = logging.INFO,
    add_stream_handler: bool = False,
) -> logging.Logger:
    """Налаштовує запис у лог-файл (викликається з cli.py або dashboard.py)."""
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == path.resolve():
            return logger

    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [TASK %(task_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(level)

    if add_stream_handler:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def log_status_change(func: F) -> F:
    """Декоратор для методу зміни статусу завдання (Task.change_status).

    Фіксує в журналі:
    - ID та назву завдання;
    - Статус до виклику і статус після виклику;
    - Помилкові спроби невалідних переходів.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        target_obj = args[0] if args else None

        task_id = getattr(target_obj, "id", "UNKNOWN")
        task_title = getattr(target_obj, "title", "Без назви")

        old_status_raw = getattr(target_obj, "status", None)
        old_status_val = (
            old_status_raw.value if hasattr(old_status_raw, "value") else str(old_status_raw)
        )

        new_status_arg = None
        if len(args) > 1:
            new_status_arg = args[1]
        elif "new_status" in kwargs:
            new_status_arg = kwargs["new_status"]
        elif "status" in kwargs:
            new_status_arg = kwargs["status"]

        target_status_val = (
            new_status_arg.value
            if hasattr(new_status_arg, "value")
            else (str(new_status_arg) if new_status_arg is not None else "UNKNOWN")
        )

        extra_info = {"task_id": task_id}

        try:
            result = func(*args, **kwargs)

            curr_status_raw = getattr(target_obj, "status", new_status_arg)
            curr_status_val = (
                curr_status_raw.value
                if hasattr(curr_status_raw, "value")
                else str(curr_status_raw)
            )

            logger.info(
                f"'{task_title}': зміна статусу {old_status_val} -> {curr_status_val}",
                extra=extra_info,
            )
            return result

        except Exception as exc:
            logger.warning(
                f"'{task_title}': невдала спроба зміни {old_status_val} -> "
                f"{target_status_val} ({exc.__class__.__name__}: {exc})",
                extra=extra_info,
            )
            raise

    return wrapper  # type: ignore[return-value]


def read_status_logs(log_file: str | Path = "logs/status_changes.log") -> list[dict[str, str]]:
    """Парсить історію переходів з лог-файлу для відображення на дашборді."""
    path = Path(log_file)
    if not path.is_file():
        return []

    entries: list[dict[str, str]] = []
    pattern = re.compile(
        r"^\[(?P<timestamp>[^\]]+)\]\s+\[(?P<level>[^\]]+)\]\s+\[TASK\s+(?P<task_id>[^\]]+)\]\s+(?P<message>.*)$"
    )

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                match = pattern.match(line)
                if match:
                    entries.append(match.groupdict())
                else:
                    entries.append(
                        {"timestamp": "", "level": "INFO", "task_id": "-", "message": line}
                    )
    except Exception:
        return []

    return entries
