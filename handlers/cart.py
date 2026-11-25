from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Cart, Product
from keyboards.inline import CartCallback, ProductCallback, get_cart_kb
from services.cart_service import add_item_to_cart, clear_user_cart, get_cart
from utils.texts import Buttons, Messages

cart_router = Router()


@cart_router.callback_query(ProductCallback.filter(F.action == "add_cart"))
async def add_to_cart_handler(call: CallbackQuery, callback_data: ProductCallback, session: AsyncSession):
    """Ловит нажатие кнопки 'Добавить в корзину' и проверяет наличие товара на складе."""
    prod_result = await session.execute(select(Product).where(Product.id == callback_data.product_id))
    product = prod_result.scalar_one_or_none()

    if not product:
        await call.answer("❌ Товар не найден.", show_alert=True)
        return

    if product.stock <= 0:
        await call.answer("❌ К сожалению, товара сейчас нет в наличии.", show_alert=True)
        return

    cart_result = await session.execute(
        select(Cart).where(
            Cart.user_id == call.from_user.id,
            Cart.product_id == product.id,
        )
    )
    existing_item = cart_result.scalars().first()
    current_in_cart = existing_item.quantity if existing_item else 0

    if current_in_cart + callback_data.quantity > product.stock:
        await call.answer(
            f"⚠️ На складе доступно только {product.stock} шт. (в корзине уже {current_in_cart} шт.).",
            show_alert=True,
        )
        return

    await add_item_to_cart(
        session=session,
        user_id=call.from_user.id,
        product_id=callback_data.product_id,
        quantity=callback_data.quantity,
    )
    await call.answer("✅ Товар успешно добавлен в корзину!", show_alert=True)


@cart_router.message(F.text == Buttons.CART)
async def show_cart_handler(message: Message, session: AsyncSession):
    """Открывает корзину и подсчитывает итоговую сумму."""
    cart_items = await get_cart(session, message.from_user.id)

    if not cart_items:
        await message.answer(Messages.CART_EMPTY)
        return

    items_text = ""
    total_price = 0.0

    for i, item in enumerate(cart_items, start=1):
        if not item.product:
            continue
        cost = item.quantity * item.product.price
        total_price += cost
        items_text += f"{i}. {escape(item.product.title)} — {item.quantity} шт. (<b>{cost:.2f} руб.</b>)\n"

    if not items_text:
        await message.answer(Messages.CART_EMPTY)
        return

    text = Messages.CART_TOTAL.format(
        items=items_text,
        total=round(total_price, 2),
    )

    await message.answer(text=text, reply_markup=get_cart_kb())


@cart_router.callback_query(CartCallback.filter(F.action == "clear"))
async def clear_cart_handler(call: CallbackQuery, session: AsyncSession):
    """Очищает корзину по нажатию на Inline-кнопку."""
    await clear_user_cart(session, call.from_user.id)

    try:
        await call.message.edit_text(Messages.CART_EMPTY)
    except TelegramBadRequest:
        pass
    await call.answer("Корзина очищена")