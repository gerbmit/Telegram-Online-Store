from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Category, Favorite, Product
from keyboards.inline import (
    CategoryCallback,
    ProductCallback,
    get_categories_kb,
    get_product_kb,
    get_products_list_kb,
)
from utils.texts import Messages

product_router = Router()


@product_router.callback_query(CategoryCallback.filter())
async def show_products_in_category(call: CallbackQuery, callback_data: CategoryCallback, session: AsyncSession):
    """Обрабатывает нажатие на категорию и выводит список товаров."""
    result = await session.execute(
        select(Product).where(Product.category_id == callback_data.category_id)
    )
    products = result.scalars().all()

    if not products:
        await call.answer("В этой категории пока нет товаров.", show_alert=True)
        return

    try:
        await call.message.edit_text(
            text="Выберите товар:",
            reply_markup=get_products_list_kb(products),
        )
    except TelegramBadRequest:
        await call.message.answer(
            text="Выберите товар:",
            reply_markup=get_products_list_kb(products),
        )
    await call.answer()


@product_router.callback_query(ProductCallback.filter(F.action == "view"))
async def show_product_card(call: CallbackQuery, callback_data: ProductCallback, session: AsyncSession):
    """Показывает карточку конкретного товара с фото и описанием."""
    result = await session.execute(
        select(Product).where(Product.id == callback_data.product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return

    fav_result = await session.execute(
        select(Favorite).where(
            Favorite.user_id == call.from_user.id,
            Favorite.product_id == product.id,
        )
    )
    in_favorites = fav_result.scalars().first() is not None

    caption = Messages.PRODUCT_CAPTION.format(
        title=escape(product.title),
        description=escape(product.description or "Нет описания"),
        stock=product.stock,
        article=escape(product.article or "-"),
        price=round(product.price, 2),
    )

    kb = get_product_kb(product_id=product.id, current_qty=1, in_favorites=in_favorites)

    # Удаляем предыдущее сообщение безопасно (если уже удалено или старше 48 часов — не падаем)
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass

    if product.photo:
        await call.message.answer_photo(photo=product.photo, caption=caption, reply_markup=kb)
    else:
        await call.message.answer(text=caption, reply_markup=kb)

    await call.answer()


@product_router.callback_query(ProductCallback.filter(F.action.in_(["plus", "minus"])))
async def change_product_quantity(call: CallbackQuery, callback_data: ProductCallback, session: AsyncSession):
    """Изменяет количество товара на карточке с проверкой остатка на складе."""
    prod_result = await session.execute(select(Product).where(Product.id == callback_data.product_id))
    product = prod_result.scalar_one_or_none()

    if not product:
        await call.answer("Товар не найден.", show_alert=True)
        return

    new_qty = callback_data.quantity

    if callback_data.action == "plus":
        if product.stock <= 0:
            await call.answer("❌ Товара нет в наличии.", show_alert=True)
            return
        if new_qty >= product.stock:
            await call.answer(f"⚠️ На складе доступно только {product.stock} шт.", show_alert=True)
            return
        new_qty += 1
    elif callback_data.action == "minus" and new_qty > 1:
        new_qty -= 1

    if new_qty == callback_data.quantity:
        await call.answer()
        return

    fav_result = await session.execute(
        select(Favorite).where(
            Favorite.user_id == call.from_user.id,
            Favorite.product_id == callback_data.product_id,
        )
    )
    in_favorites = fav_result.scalars().first() is not None

    try:
        await call.message.edit_reply_markup(
            reply_markup=get_product_kb(
                product_id=callback_data.product_id,
                current_qty=new_qty,
                in_favorites=in_favorites,
            )
        )
    except TelegramBadRequest:
        pass
    await call.answer()


@product_router.callback_query(ProductCallback.filter(F.action == "fav"))
async def toggle_favorite(call: CallbackQuery, callback_data: ProductCallback, session: AsyncSession):
    """Добавление или удаление товара из избранного (защищено от двойного клика)."""
    user_id = call.from_user.id
    product_id = callback_data.product_id

    result = await session.execute(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.product_id == product_id)
    )
    fav_items = result.scalars().all()

    in_favorites = False
    if fav_items:
        for fav_item in fav_items:
            await session.delete(fav_item)
        await session.commit()
        await call.answer("💔 Удалено из избранного", show_alert=False)
    else:
        session.add(Favorite(user_id=user_id, product_id=product_id))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
        in_favorites = True
        await call.answer("❤️ Добавлено в избранное", show_alert=False)

    try:
        await call.message.edit_reply_markup(
            reply_markup=get_product_kb(
                product_id=product_id,
                current_qty=callback_data.quantity,
                in_favorites=in_favorites,
            )
        )
    except TelegramBadRequest:
        pass


@product_router.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(call: CallbackQuery, session: AsyncSession):
    """Кнопка 'Назад': возвращает к списку категорий."""
    result = await session.execute(select(Category))
    categories = result.scalars().all()

    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass

    await call.message.answer(
        text=Messages.CHOOSE_CATEGORY,
        reply_markup=get_categories_kb(list(categories)),
    )
    await call.answer()


@product_router.callback_query(F.data == "ignore")
async def ignore_callback(call: CallbackQuery):
    """Гасит индикатор загрузки при клике на неинтерактивную кнопку счётчика."""
    await call.answer()