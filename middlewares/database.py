from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker

class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware для автоматической передачи сессии базы данных в обработчики (handlers).
    Реализует паттерн Dependency Injection для сессий БД.
    """
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Открываем сессию при каждом входящем событии от Telegram
        async with self.session_pool() as session:
            # Кладем объект сессии в словарь `data`
            # Теперь любой обработчик может принять аргумент `session: AsyncSession`
            data["session"] = session
            # Передаем управление дальше по цепочке
            return await handler(event, data)