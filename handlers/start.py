from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from keyboards.reply import get_main_menu
from utils.logger import logger
from utils.texts import Messages

# Роутер для стартовой команды и регистрации
start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """
    Обработчик команды /start.
    Сбрасывает активное состояние FSM, регистрирует нового пользователя
    (или актуализирует имя/username существующего) и открывает главное меню.
    """
    await state.clear()

    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        new_user = User(
            id=user_id,
            name=first_name,
            username=username,
        )
        session.add(new_user)
        try:
            await session.commit()
            logger.info(f"Новый пользователь зарегистрирован: {user_id}")
        except IntegrityError:
            # Защита от двойного быстрого нажатия /start
            await session.rollback()
    else:
        # Обновляем имя или username, если пользователь изменил их в Telegram
        if user.name != first_name or user.username != username:
            user.name = first_name
            user.username = username
            await session.commit()

    await message.answer(
        text=Messages.WELCOME,
        reply_markup=get_main_menu(),
    )