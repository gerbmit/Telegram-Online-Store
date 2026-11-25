from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import config
from keyboards.inline import SupportCallback, get_support_reply_kb
from utils.logger import logger
from utils.states import SupportState
from utils.texts import Buttons

support_router = Router()


@support_router.message(Command("cancel"), StateFilter(SupportState))
@support_router.message(F.text.casefold() == "отмена", StateFilter(SupportState))
async def cancel_support(message: Message, state: FSMContext):
    """Позволяет пользователю или админу выйти из режима поддержки."""
    await state.clear()
    await message.answer("❌ Обращение в поддержку отменено.")


@support_router.message(F.text == Buttons.SUPPORT)
async def ask_support(message: Message, state: FSMContext):
    """Переводит пользователя в режим ожидания ввода вопроса."""
    await state.set_state(SupportState.waiting_for_question)
    await message.answer(
        "💬 Напишите ваш вопрос одним сообщением, и я передам его администраторам.\n"
        "Для отмены отправьте «отмена» или /cancel."
    )


@support_router.message(SupportState.waiting_for_question)
async def receive_question(message: Message, state: FSMContext, bot: Bot):
    """Получает вопрос и безопасно рассылает его всем админам."""
    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, отправьте текстовое сообщение.")
        return

    user = message.from_user
    if user.username:
        sender = f"@{escape(user.username)} (ID: <code>{user.id}</code>)"
    else:
        sender = f"{escape(user.first_name or 'Пользователь')} (ID: <code>{user.id}</code>)"

    question_text = (
        f"❗️ <b>Новое обращение в поддержку</b>\n\n"
        f"От: {sender}\n\n"
        f"Текст:\n<i>{escape(message.text.strip())}</i>"
    )

    delivered = 0
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=question_text,
                reply_markup=get_support_reply_kb(user.id),
            )
            delivered += 1
        except Exception as err:
            logger.warning(f"Не удалось доставить обращение админу {admin_id}: {err}")

    await state.clear()

    if delivered > 0:
        await message.answer("✅ Ваш вопрос отправлен! Мы ответим вам в ближайшее время.")
    else:
        await message.answer("⚠️ Сейчас не удалось связаться с поддержкой. Попробуйте позже.")


@support_router.callback_query(SupportCallback.filter())
async def admin_reply_callback(call: CallbackQuery, callback_data: SupportCallback, state: FSMContext):
    """Срабатывает, когда админ нажал кнопку 'Ответить'."""
    if call.from_user.id not in config.ADMIN_IDS:
        await call.answer("Нет прав", show_alert=True)
        return

    await state.update_data(reply_to_user=callback_data.user_id)
    await state.set_state(SupportState.waiting_for_answer)
    await call.message.answer(
        f"✍️ Напишите ответ для пользователя <code>{callback_data.user_id}</code> "
        f"(или отправьте /cancel для отмены):"
    )
    await call.answer()


@support_router.message(SupportState.waiting_for_answer)
async def send_reply_to_user(message: Message, state: FSMContext, bot: Bot):
    """Отправляет ответ от админа пользователю с экранированием HTML."""
    if message.from_user.id not in config.ADMIN_IDS:
        await state.clear()
        return

    if not message.text or not message.text.strip():
        await message.answer("Пожалуйста, отправьте текстовый ответ (или /cancel для отмены).")
        return

    data = await state.get_data()
    user_id = data.get("reply_to_user")

    if not user_id:
        await state.clear()
        await message.answer("❌ Не удалось определить получателя. Нажмите «Ответить» повторно.")
        return

    reply_text = f"👨‍💻 <b>Ответ от поддержки:</b>\n\n{escape(message.text.strip())}"

    try:
        await bot.send_message(chat_id=user_id, text=reply_text)
        await message.answer("✅ Ответ успешно отправлен пользователю.")
    except Exception as err:
        logger.warning(f"Не удалось отправить ответ пользователю {user_id}: {err}")
        await message.answer("❌ Не удалось отправить ответ. Возможно, пользователь заблокировал бота.")

    await state.clear()