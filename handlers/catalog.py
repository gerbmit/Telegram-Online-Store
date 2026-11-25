# handlers/catalog.py
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import Category
from keyboards.inline import get_categories_kb
from utils.texts import Messages, Buttons

catalog_router = Router()

@catalog_router.message(F.text == Buttons.CATALOG)
async def show_catalog(message: Message, session: AsyncSession):
    """
    Обработчик нажатия на кнопку "🛍 Каталог".
    Достает все категории из БД и формирует Inline-клавиатуру.
    """
    # Получаем все категории
    result = await session.execute(select(Category))
    categories = result.scalars().all()
    
    if not categories:
        await message.answer(Messages.CATALOG_EMPTY)
        return
        
    await message.answer(
        text=Messages.CHOOSE_CATEGORY,
        reply_markup=get_categories_kb(list(categories))
    )