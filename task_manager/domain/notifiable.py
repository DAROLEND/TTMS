from abc import ABC, abstractmethod


class Notifiable(ABC):
    @abstractmethod
    def get_notification_message(self) -> str:
        """Формує текст сповіщення. Нічого не відправляє."""
