from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Cart


async def add_item_to_cart(session: AsyncSession, user_id: int, product_id: int, quantity: int) -> None:
    """
    Добавляет товар в корзину пользователя.
    Если товар уже есть, увеличивает его количество. Защищено от двойного клика.
    """
    result = await session.execute(
        select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
    )
    cart_item = result.scalars().first()

    if cart_item:
        cart_item.quantity += quantity
        await session.commit()
        return

    cart_item = Cart(user_id=user_id, product_id=product_id, quantity=quantity)
    session.add(cart_item)
    try:
        await session.commit()
    except IntegrityError:
        # Если параллельный запрос успел создать запись — откатываем и обновляем существующую
        await session.rollback()
        result = await session.execute(
            select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
        )
        existing = result.scalars().first()
        if existing:
            existing.quantity += quantity
            await session.commit()


async def get_cart(session: AsyncSession, user_id: int) -> list[Cart]:
    """
    Возвращает все товары в корзине пользователя вместе со связанными объектами Product.
    """
    result = await session.execute(
        select(Cart)
        .options(joinedload(Cart.product))
        .where(Cart.user_id == user_id)
    )
    return list(result.scalars().all())


async def clear_user_cart(session: AsyncSession, user_id: int) -> None:
    """Полностью очищает корзину конкретного пользователя."""
    await session.execute(
        delete(Cart).where(Cart.user_id == user_id)
    )
    await session.commit()