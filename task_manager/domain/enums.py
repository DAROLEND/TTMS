from enum import Enum


class Status(Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

    @property
    def label(self) -> str:
        return _STATUS_LABELS[self]

    @property
    def is_final(self) -> bool:
        return self in (Status.DONE, Status.CANCELLED)


class Priority(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def label(self) -> str:
        return _PRIORITY_LABELS[self]


_STATUS_LABELS = {
    Status.TODO: "До виконання",
    Status.IN_PROGRESS: "У роботі",
    Status.REVIEW: "На перевірці",
    Status.DONE: "Виконано",
    Status.CANCELLED: "Скасовано",
}

_PRIORITY_LABELS = {
    Priority.LOW: "Низький",
    Priority.MEDIUM: "Середній",
    Priority.HIGH: "Високий",
    Priority.CRITICAL: "Критичний",
}
