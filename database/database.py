from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from config import config

# Создаем асинхронный движок для подключения к БД. 
# echo=False отключает вывод всех SQL-запросов в консоль (можно включить для дебага).
engine = create_async_engine(config.DB_URL, echo=False)

# Фабрика сессий для взаимодействия с базой данных
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    """
    Базовый класс для всех моделей.
    Наследует DeclarativeBase (SQLAlchemy 2.0) и AsyncAttrs для поддержки ленивой загрузки (lazy load) в асинхронном коде.
    """
    pass

async def init_db():
    """
    Инициализация базы данных. 
    Создает все таблицы, описанные в моделях, если они еще не созданы.
    Для production лучше использовать миграции (Alembic), но на старте это сэкономит время.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)