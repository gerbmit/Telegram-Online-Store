import asyncio
import math
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import config
from database.models import Category, Order, Product, User
from keyboards.inline import (
    AdminCategoryCallback,
    AdminDeleteCatCallback,
    AdminManageCatCallback,
    AdminOrderFilterCallback,
    AdminOrderStatusCallback,
    AdminProductManageCallback,
    get_admin_categories_kb,
    get_admin_manage_categories_kb,
    get_admin_order_filters_kb,
    get_admin_order_status_kb,
    get_admin_products_kb,
)
from keyboards.reply import get_admin_menu, get_main_menu
from services.order_service import restore_order_stock
from utils.states import AdminBroadcastState, AdminCategoryState, AdminProductState
from utils.texts import Buttons

admin_router = Router()

# Фильтр автоматически отсекает всех пользователей, чьих ID нет в config.ADMIN_IDS
admin_router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
admin_router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))


@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    """Главное меню админ-панели."""
    await message.answer(
        "🛠 <b>Панель администратора</b>\n\nВыберите действие:",
        reply_markup=get_admin_menu(),
    )


@admin_router.message(F.text == Buttons.ADMIN_EXIT)
async def exit_admin(message: Message, state: FSMContext):
    """Выход из админки в обычное меню."""
    await state.clear()
    await message.answer("Вы вышли из админ-панели.", reply_markup=get_main_menu())


@admin_router.message(Command("cancel"), StateFilter("*"))
@admin_router.message(F.text.casefold() == "отмена", StateFilter("*"))
async def cancel_handler(message: Message, state: FSMContext):
    """Универсальная отмена любого действия (FSM) для администратора."""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_admin_menu())


# ==========================================
# УПРАВЛЕНИЕ ТОВАРАМИ И ЗАКАЗАМИ
# ==========================================

@admin_router.message(F.text == Buttons.ADMIN_PRODUCTS)
async def manage_products(message: Message, session: AsyncSession):
    """Вывод списка товаров для удаления."""
    result = await session.execute(select(Product))
    products = result.scalars().all()

    if not products:
        await message.answer("📦 Товаров пока нет.")
        return

    await message.answer(
        "📦 <b>Управление товарами</b>\nНажмите на товар, чтобы удалить его:",
        reply_markup=get_admin_products_kb(list(products)),
    )


@admin_router.callback_query(AdminProductManageCallback.filter(F.action == "delete"))
async def delete_product(call: CallbackQuery, callback_data: AdminProductManageCallback, session: AsyncSession):
    """Удаление товара."""
    result = await session.execute(select(Product).where(Product.id == callback_data.product_id))
    product = result.scalar_one_or_none()

    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return

    title = product.title
    try:
        await session.delete(product)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await call.answer("❌ Не удалось удалить товар: он связан с существующими записями в БД.", show_alert=True)
        return

    await call.answer(f"✅ Товар '{title}' удален!", show_alert=True)

    # Перерисовываем список оставшихся товаров
    res = await session.execute(select(Product))
    prods = res.scalars().all()
    try:
        if prods:
            await call.message.edit_reply_markup(reply_markup=get_admin_products_kb(list(prods)))
        else:
            await call.message.edit_text("📦 Товаров больше нет.")
    except TelegramBadRequest:
        pass


@admin_router.message(F.text == Buttons.ADMIN_ORDERS)
async def admin_orders_menu(message: Message):
    """Меню фильтрации заказов."""
    await message.answer(
        "🧾 <b>Управление заказами</b>\n\nВыберите статус заказов для просмотра:",
        reply_markup=get_admin_order_filters_kb(),
    )


@admin_router.callback_query(AdminOrderFilterCallback.filter())
async def show_filtered_orders(call: CallbackQuery, callback_data: AdminOrderFilterCallback, session: AsyncSession):
    """Вывод списка заказов по выбранному статусу."""
    result = await session.execute(
        select(Order)
        .where(Order.status == callback_data.status)
        .order_by(desc(Order.created_at))
        .limit(5)
    )
    orders = result.scalars().all()

    if not orders:
        await call.answer(f"Заказов со статусом '{callback_data.status}' нет.", show_alert=True)
        return

    await call.message.answer(f"📦 <b>Последние заказы со статусом '{escape(callback_data.status)}':</b>")

    for order in orders:
        date_str = order.created_at.strftime("%d.%m.%Y %H:%M")
        text = (
            f"🔹 <b>Заказ №{order.id}</b>\n"
            f"👤 Клиент: {escape(order.name)} ({escape(order.phone)})\n"
            f"🏠 Адрес: {escape(order.city)}, {escape(order.address)}\n"
            f"💬 Коммент: {escape(order.comment or '-')}\n"
            f"💰 Сумма: {order.total_price:.2f} руб.\n"
            f"📅 Дата: {date_str}\n"
            f"Текущий статус: <b>{escape(order.status)}</b>"
        )
        # Скрываем кнопки изменения статуса для завершенных и отмененных заказов
        kb = None if order.status in ["Завершен", "Отменен"] else get_admin_order_status_kb(order.id)
        await call.message.answer(text, reply_markup=kb)

    await call.answer()


@admin_router.callback_query(AdminOrderStatusCallback.filter())
async def change_order_status(call: CallbackQuery, callback_data: AdminOrderStatusCallback, session: AsyncSession):
    """Изменение статуса конкретного заказа."""
    result = await session.execute(select(Order).where(Order.id == callback_data.order_id))
    order = result.scalar_one_or_none()

    if not order:
        await call.answer("Заказ не найден!", show_alert=True)
        return

    old_status = order.status
    order.status = callback_data.status

    # Если заказ перевели в "Отменен", возвращаем его позиции на склад
    if callback_data.status == "Отменен" and old_status != "Отменен":
        await restore_order_stock(session, order.id)

    await session.commit()

    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await call.message.reply(f"✅ Статус заказа №{order.id} изменен на <b>{escape(order.status)}</b>.")
    await call.answer()


# ==========================================
# УПРАВЛЕНИЕ КАТЕГОРИЯМИ (FSM)
# ==========================================

@admin_router.message(F.text == Buttons.ADMIN_CATEGORIES)
async def manage_categories(message: Message, session: AsyncSession):
    result = await session.execute(select(Category))
    categories = result.scalars().all()
    await message.answer(
        "📂 <b>Управление категориями</b>\n\nВыберите действие или удалите существующую категорию:",
        reply_markup=get_admin_manage_categories_kb(list(categories)),
    )


@admin_router.callback_query(AdminDeleteCatCallback.filter())
async def delete_category(call: CallbackQuery, callback_data: AdminDeleteCatCallback, session: AsyncSession):
    result = await session.execute(select(Category).where(Category.id == callback_data.category_id))
    category = result.scalar_one_or_none()

    if not category:
        await call.answer("Категория не найдена.", show_alert=True)
        return

    try:
        await session.delete(category)
        await session.commit()
        await call.answer(f"✅ Категория '{category.name}' удалена!", show_alert=True)
    except IntegrityError:
        await session.rollback()
        await call.answer("❌ Нельзя удалить категорию, в которой есть товары!", show_alert=True)
        return

    # Обновляем список категорий
    res = await session.execute(select(Category))
    cats = res.scalars().all()
    try:
        await call.message.edit_reply_markup(reply_markup=get_admin_manage_categories_kb(list(cats)))
    except TelegramBadRequest:
        pass


@admin_router.callback_query(AdminManageCatCallback.filter(F.action == "add"))
async def add_category_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminCategoryState.waiting_for_category_name)
    try:
        await call.message.edit_text("📝 Введите название новой категории (или /cancel для отмены):")
    except TelegramBadRequest:
        await call.message.answer("📝 Введите название новой категории (или /cancel для отмены):")
    await call.answer()


@admin_router.message(AdminCategoryState.waiting_for_category_name)
async def add_category_name(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text or not message.text.strip():
        await message.answer("Ошибка! Пожалуйста, отправьте текстовое название категории.")
        return

    category_name = message.text.strip()
    new_category = Category(name=category_name)
    session.add(new_category)

    try:
        await session.commit()
        await message.answer(f"✅ Категория <b>{escape(category_name)}</b> успешно добавлена!")
    except IntegrityError:
        await session.rollback()
        await message.answer(f"❌ Категория <b>{escape(category_name)}</b> уже существует. Придумайте другое название.")
    finally:
        await state.clear()


# ==========================================
# ДОБАВЛЕНИЕ ТОВАРА (FSM)
# ==========================================

@admin_router.message(F.text == Buttons.ADMIN_ADD_PRODUCT)
async def add_product_start(message: Message, state: FSMContext):
    await state.set_state(AdminProductState.waiting_for_title)
    await message.answer("Введите название товара (или отправьте /cancel для отмены):")


@admin_router.message(AdminProductState.waiting_for_title)
async def add_product_title(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Ошибка! Введите текстовое название товара.")
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(AdminProductState.waiting_for_description)
    await message.answer("Введите описание товара:")


@admin_router.message(AdminProductState.waiting_for_description)
async def add_product_desc(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Ошибка! Введите текстовое описание товара.")
        return

    await state.update_data(description=message.text.strip())
    await state.set_state(AdminProductState.waiting_for_price)
    await message.answer("Введите цену (положительное число, например 1500.50):")


@admin_router.message(AdminProductState.waiting_for_price)
async def add_product_price(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Ошибка! Пожалуйста, отправьте корректное число.")
        return

    try:
        price = float(message.text.strip().replace(",", "."))
        if not math.isfinite(price) or price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Ошибка! Цена должна быть положительным числом (например, 1500.50).")
        return

    await state.update_data(price=round(price, 2))
    await state.set_state(AdminProductState.waiting_for_photo)
    await message.answer("Отправьте фото товара:")


@admin_router.message(AdminProductState.waiting_for_photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext):
    # Берем ID картинки лучшего качества (последнюю в массиве)
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(AdminProductState.waiting_for_stock)
    await message.answer("Введите количество товара на складе (целое число, от 0):")


@admin_router.message(AdminProductState.waiting_for_photo)
async def add_product_photo_invalid(message: Message):
    await message.answer("Ошибка! Пожалуйста, отправьте именно фотографию товара (не документ и не текст).")


@admin_router.message(AdminProductState.waiting_for_stock)
async def add_product_stock(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text:
        await message.answer("Ошибка! Отправьте целое число (0 или больше).")
        return

    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("Ошибка! Отправьте целое неотрицательное число (например, 10).")
        return

    await state.update_data(stock=stock)

    # Достаем категории для выбора
    result = await session.execute(select(Category))
    categories = result.scalars().all()

    if not categories:
        await state.clear()
        await message.answer("❌ Нет доступных категорий. Сначала создайте категорию!")
        return

    await state.set_state(AdminProductState.waiting_for_category)
    await message.answer("Выберите категорию:", reply_markup=get_admin_categories_kb(list(categories)))


@admin_router.callback_query(AdminProductState.waiting_for_category, AdminCategoryCallback.filter())
async def add_product_finish(
    call: CallbackQuery,
    callback_data: AdminCategoryCallback,
    state: FSMContext,
    session: AsyncSession,
):
    data = await state.get_data()

    new_product = Product(
        title=data["title"],
        description=data["description"],
        price=data["price"],
        photo=data["photo"],
        stock=data["stock"],
        category_id=callback_data.category_id,
    )
    session.add(new_product)
    await session.commit()

    await state.clear()
    try:
        await call.message.edit_text(f"✅ Товар <b>{escape(data['title'])}</b> успешно добавлен!")
    except TelegramBadRequest:
        await call.message.answer(f"✅ Товар <b>{escape(data['title'])}</b> успешно добавлен!")
    await call.answer()


# ==========================================
# РАССЫЛКА (BROADCAST)
# ==========================================

@admin_router.message(F.text == Buttons.ADMIN_BROADCAST)
async def start_broadcast(message: Message, state: FSMContext):
    """Запуск рассылки всем пользователям."""
    await state.set_state(AdminBroadcastState.waiting_for_message)
    await message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение (текст, фото, видео или документ), которое получат все пользователи.\n"
        "Для отмены отправьте /cancel"
    )


@admin_router.message(AdminBroadcastState.waiting_for_message)
async def process_broadcast(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Обрабатывает полученное сообщение и рассылает пользователям с учетом лимитов Telegram."""
    result = await session.execute(select(User.id))
    user_ids = result.scalars().all()

    await state.clear()
    await message.answer(f"⏳ Начинаю рассылку по <b>{len(user_ids)}</b> пользователям...")

    sent_count = 0
    for uid in user_ids:
        try:
            await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            sent_count += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
                sent_count += 1
            except Exception:
                pass
        except Exception:
            pass  # Игнорируем пользователей, заблокировавших бота

        # Пауза для соблюдения лимита Telegram (~20 сообщений/сек)
        await asyncio.sleep(0.05)

    await message.answer(f"✅ Рассылка завершена!\nДоставлено: <b>{sent_count}</b> из {len(user_ids)}.")


# ==========================================
# СТАТИСТИКА
# ==========================================

@admin_router.message(F.text == Buttons.ADMIN_STATS)
async def show_statistics(message: Message, session: AsyncSession):
    """Сбор и вывод общей статистики магазина."""
    users_count = await session.scalar(select(func.count(User.id))) or 0
    products_count = await session.scalar(select(func.count(Product.id))) or 0
    orders_count = await session.scalar(select(func.count(Order.id))) or 0

    total_revenue = await session.scalar(
        select(func.sum(Order.total_price))
        .where(Order.status.in_(["Оплачен", "Завершен"]))
    )
    total_revenue = total_revenue or 0.0

    text = (
        "📊 <b>Статистика магазина</b>\n\n"
        f"👥 Пользователей: <b>{users_count}</b>\n"
        f"📦 Товаров в каталоге: <b>{products_count}</b>\n"
        f"🧾 Всего заказов: <b>{orders_count}</b>\n"
        f"💰 Общий доход: <b>{total_revenue:.2f} руб.</b>"
    )
    await message.answer(text)