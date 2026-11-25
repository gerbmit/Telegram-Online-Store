import logging

from aiogram import Bot, F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Order

payment_router = Router()


@payment_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery, session: AsyncSession, bot: Bot):
    """Предварительная проверка перед списанием средств."""
    try:
        order_id = int(pre_checkout_query.invoice_payload)
    except ValueError:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Некорректный идентификатор заказа!",
        )
        return

    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Заказ не найден!",
        )
        return

    if order.status != "Новый":
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Этот заказ уже оплачен или отменен!",
        )
        return

    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@payment_router.message(F.successful_payment)
async def process_successful_payment(message: Message, session: AsyncSession):
    """Обрабатывает факт успешного списания средств от провайдера."""
    payment = message.successful_payment
    try:
        order_id = int(payment.invoice_payload)
    except ValueError:
        logging.error(f"Некорректный payload успешной оплаты: {payment.invoice_payload}")
        await message.answer("✅ Оплата получена, но не удалось определить номер заказа. Напишите в поддержку.")
        return

    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        logging.error(f"Заказ №{order_id} не найден после успешной оплаты.")
        await message.answer(
            f"✅ Оплата получена, но заказ №{order_id} не найден в базе. Пожалуйста, свяжитесь с поддержкой."
        )
        return

    order.status = "Оплачен"
    await session.commit()

    # Telegram Stars (XTR) приходят целым числом, фиатные валюты — в минимальных единицах (копейках)
    if payment.currency == "XTR":
        amount_str = str(payment.total_amount)
    else:
        amount_str = f"{payment.total_amount / 100:.2f}"

    await message.answer(
        f"🎉 <b>Оплата прошла успешно!</b>\n\n"
        f"Ваш заказ №{order.id} оплачен.\n"
        f"Сумма: {amount_str} {payment.currency}.\n"
        f"Статус заказа можно отслеживать в разделе «📦 Мои заказы»."
    )