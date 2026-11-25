from html import escape

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Favorite, Order, Product, User
from keyboards.inline import get_products_list_kb
from utils.texts import Buttons

profile_router = Router()


@profile_router.message(F.text == Buttons.PROFILE)
async def show_profile(message: Message, session: AsyncSession):
    """Выводит профиль пользователя со статистикой заказов."""
    user_id = message.from_user.id

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        await message.answer("⚠️ Профиль не найден. Пожалуйста, отправьте /start для регистрации.")
        return

    stats_result = await session.execute(
        select(func.count(Order.id), func.sum(Order.total_price))
        .where(Order.user_id == user_id, Order.status != "Отменен")
    )
    orders_count, total_spent = stats_result.one()
    total_spent = total_spent or 0.0

    reg_date = user.registered_at.strftime("%d.%m.%Y")
    username_str = f"@{escape(user.username)}" if user.username else "отсутствует"

    text = (
        f"👤 <b>Ваш профиль:</b>\n\n"
        f"ID: <code>{user.id}</code>\n"
        f"Имя: {escape(user.name or 'Не указано')}\n"
        f"Username: {username_str}\n"
        f"Дата регистрации: {reg_date}\n\n"
        f"📦 Количество заказов: {orders_count}\n"
        f"💰 Общая сумма покупок: {total_spent:.2f} руб."
    )
    await message.answer(text)


@profile_router.message(F.text == Buttons.FAVORITES)
async def show_favorites(message: Message, session: AsyncSession):
    """Выводит список избранных товаров."""
    result = await session.execute(
        select(Product)
        .join(Favorite)
        .where(Favorite.user_id == message.from_user.id)
    )
    products = result.scalars().all()

    if not products:
        await message.answer("⭐ Ваше избранное пока пусто.")
        return

    await message.answer(
        "⭐ Ваши избранные товары:",
        reply_markup=get_products_list_kb(products),
    )