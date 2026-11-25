import logging

def setup_logger():
    """
    Настройка базового логгирования для всего проекта.
    Позволяет отслеживать ошибки и информационные сообщения в консоли.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger = logging.getLogger("shop_bot")
    return logger

# Экземпляр логгера для импорта в другие файлы
logger = setup_logger()