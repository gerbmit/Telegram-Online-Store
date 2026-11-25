import logging
import os

from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()


def _parse_admin_ids(raw_value: str) -> list[int]:
    """Безопасно парсит список Telegram ID администраторов из строки через запятую."""
    admin_ids: list[int] = []
    for item in raw_value.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        try:
            admin_ids.append(int(cleaned))
        except ValueError:
            logging.warning(f"Некорректный ID администратора в ADMIN_IDS пропущен: '{cleaned}'")
    return admin_ids


class Config:
    """Класс для хранения конфигурации приложения."""

    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    # Токен провайдера платежей (ЮKassa, Stripe и т.д.). Для Telegram Stars оставить пустой строкой
    PAYMENT_TOKEN: str = os.getenv("PAYMENT_TOKEN", "").strip()
    ADMIN_IDS: list[int] = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    DB_URL: str = os.getenv("DB_URL", "sqlite+aiosqlite:///database.db").strip()

    def validate(self) -> None:
        """Проверяет обязательные параметры перед запуском бота."""
        if not self.BOT_TOKEN:
            raise ValueError("Не задан BOT_TOKEN! Проверьте файл .env (см. .env.example).")


config = Config()