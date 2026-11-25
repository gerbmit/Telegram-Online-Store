import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import Order
from keyboards.inline import CartCallback, ConfirmCallback, get_confirm_kb
from services.cart_service import get_cart
from services.order_service import create_order
from utils.states import OrderState
from utils.texts import Buttons

orders_router = Router()


@orders_router.message(Command("cancel"), StateFilter(OrderState))
@orders_router.message(F.text.casefold() == "отмена", StateFilter(OrderState))
async def cancel_order_fsm(message: Message, state: FSMContext):
    """Позволяет покупателю в любой момент выйти из оформления заказа."""
    await state.clear()
    await message.answer("❌ Оформление заказа отменено.")


@orders_router.message(F.text == Buttons.ORDERS)
async def show_my_orders(message: Message, session: AsyncSession):
    """Вывод истории заказов пользователя (последние 5)."""
    result = await session.execute(
        select(Order)
        .where(Order.user_id == message.from_user.id)
        .order_by(desc(Order.created_at))
        .limit(5)
    )
    orders = result.scalars().all()

    if not orders:
        await message.answer("У вас пока нет заказов 📦")
        return

    text = "📦 <b>Ваши последние заказы:</b>\n\n"
    for order in orders:
        date_str = order.created_at.strftime("%d.%m.%Y %H:%M")
        text += (
            f"🔹 <b>Заказ №{order.id}</b> от {date_str}\n"
            f"Сумма: {order.total_price:.2f} руб.\n"
            f"Статус: <b>{escape(order.status)}</b>\n"
            f"〰️〰️〰️〰️〰️〰️\n"
        )
    await message.answer(text)


@orders_router.callback_query(CartCallback.filter(F.action == "checkout"))
async def start_checkout(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начало оформления заказа."""
    cart_items = await get_cart(session, call.from_user.id)
    if not cart_items:
        await call.answer("Корзина пуста!", show_alert=True)
        return

    await state.set_state(OrderState.waiting_for_name)
    await call.message.answer("📝 Введите ваше ФИО (или отправьте «отмена» для выхода):")
    await call.answer()


@orders_router.message(OrderState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введите ваше ФИО текстом.")
        return

    await state.update_data(name=message.text.strip())
    await state.set_state(OrderState.waiting_for_phone)
    await message.answer("📱 Введите ваш номер телефона:")


@orders_router.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введите номер телефона текстом.")
        return

    await state.update_data(phone=message.text.strip())
    await state.set_state(OrderState.waiting_for_city)
    await message.answer("🏙 Введите ваш город:")


@orders_router.message(OrderState.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введите название города текстом.")
        return

    await state.update_data(city=message.text.strip())
    await state.set_state(OrderState.waiting_for_address)
    await message.answer("🏠 Введите адрес доставки:")


@orders_router.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, введите адрес доставки текстом.")
        return

    await state.update_data(address=message.text.strip())
    await state.set_state(OrderState.waiting_for_comment)
    await message.answer("💬 Оставьте комментарий к заказу (или отправьте '-', если нет):")


@orders_router.message(OrderState.waiting_for_comment)
async def process_comment(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте комментарий текстом (или '-' без комментария).")
        return

    raw_comment = message.text.strip()
    comment = raw_comment if raw_comment != "-" else None
    await state.update_data(comment=comment)

    data = await state.get_data()

    summary = (
        "<b>Проверьте данные заказа:</b>\n\n"
        f"👤 Имя: {escape(data['name'])}\n"
        f"📱 Телефон: {escape(data['phone'])}\n"
        f"🏙 Город: {escape(data['city'])}\n"
        f"🏠 Адрес: {escape(data['address'])}\n"
        f"💬 Комментарий: {escape(data['comment']) if data['comment'] else 'Нет'}\n\n"
        "Всё верно?"
    )

    await state.set_state(OrderState.confirm_order)
    await message.answer(summary, reply_markup=get_confirm_kb())


@orders_router.callback_query(ConfirmCallback.filter(), OrderState.confirm_order)
async def confirm_order(
    call: CallbackQuery,
    callback_data: ConfirmCallback,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
):
    """Обработка кнопок Подтвердить / Отменить."""
    if callback_data.action == "no":
        await state.clear()
        try:
            await call.message.edit_text("❌ Оформление заказа отменено.")
        except TelegramBadRequest:
            pass
        await call.answer()
        return

    # Создаем заказ со статусом "Новый" в БД ДО оплаты
    data = await state.get_data()
    try:
        order = await create_order(session, call.from_user.id, data)
    except ValueError as err:
        await state.clear()
        try:
            await call.message.edit_text(f"❌ {escape(str(err))}")
        except TelegramBadRequest:
            await call.message.answer(f"❌ {escape(str(err))}")
        await call.answer()
        return

    await state.clear()

    if not order:
        try:
            await call.message.edit_text("❌ Произошла ошибка. Корзина пуста.")
        except TelegramBadRequest:
            pass
        await call.answer()
        return

    try:
        # Умный выбор валюты: если токена провайдера нет, используем Telegram Stars (XTR)
        if not config.PAYMENT_TOKEN:
            currency = "XTR"
            # Звезды не имеют копеек, минимум 1 XTR
            prices = [LabeledPrice(label=f"Заказ №{order.id}", amount=max(1, round(order.total_price)))]
        else:
            currency = "RUB"
            # В рублях сумма передается в копейках (используем round вместо int, чтобы не терять копейку)
            prices = [LabeledPrice(label=f"Заказ №{order.id}", amount=round(order.total_price * 100))]

        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"Заказ №{order.id}",
            description="Оплата заказа",
            payload=str(order.id),
            provider_token=config.PAYMENT_TOKEN,
            currency=currency,
            prices=prices,
            start_parameter=f"order_{order.id}",
        )

        try:
            await call.message.edit_text(f"⏳ Заказ №{order.id} создан! Пожалуйста, оплатите счет ниже.")
        except TelegramBadRequest:
            pass
    except Exception as e:
        logging.error(f"Ошибка при выставлении счета для заказа №{order.id}: {e}")
        try:
            await call.message.edit_text(
                f"✅ Заказ №{order.id} успешно создан!\n\n"
                "⚠️ Однако возникла проблема с автоматической оплатой. Наш менеджер скоро свяжется с вами."
            )
        except TelegramBadRequest:
            pass

    await call.answer()