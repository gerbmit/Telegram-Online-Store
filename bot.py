import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from database.database import async_session, engine, init_db
from handlers.admin import admin_router
from handlers.cart import cart_router
from handlers.catalog import catalog_router
from handlers.info import info_router
from handlers.orders import orders_router
from handlers.payment import payment_router
from handlers.product import product_router
from handlers.profile import profile_router
from handlers.start import start_router
from handlers.support import support_router
from middlewares.database import DbSessionMiddleware
from utils.logger import logger


async def main() -> None:
    """
    Главная функция запуска бота.
    Проверяет конфиг, инициализирует БД, подключает middleware, роутеры и запускает polling.
    """
    config.validate()

    logger.info("Инициализация базы данных...")
    await init_db()

    logger.info("Настройка бота...")
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Подключаем middleware для автоматической передачи сессии БД в обработчики
    dp.update.middleware(DbSessionMiddleware(session_pool=async_session))

    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(product_router)
    dp.include_router(cart_router)
    dp.include_router(orders_router)
    dp.include_router(profile_router)
    dp.include_router(support_router)
    dp.include_router(admin_router)
    dp.include_router(payment_router)
    dp.include_router(info_router)

    try:
        logger.info("Бот успешно запущен и готов к работе!")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Закрытие соединений бота и базы данных...")
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ValueError as err:
        logger.error(f"Ошибка конфигурации: {err}")
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот принудительно остановлен.")