from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Cart, Order, OrderItem
from services.cart_service import get_cart


async def create_order(session: AsyncSession, user_id: int, order_data: dict) -> Order | None:
    """
    Формирует заказ на основе данных из FSM и текущей корзины пользователя.
    Проверяет наличие всех товаров на складе, списывает остатки, переносит позиции
    из Cart в OrderItem и очищает корзину в рамках одной транзакции.
    """
    cart_items = await get_cart(session, user_id)
    if not cart_items:
        return None

    # 1. Проверяем актуальность товаров и наличие нужного количества на складе
    valid_items: list[Cart] = []
    for item in cart_items:
        if not item.product:
            continue
        if item.product.stock < item.quantity:
            raise ValueError(
                f"Недостаточно товара «{item.product.title}» на складе "
                f"(доступно {item.product.stock} шт., в корзине {item.quantity} шт.)."
            )
        valid_items.append(item)

    if not valid_items:
        return None

    # Считаем итоговую сумму с округлением до копеек
    total_price = round(sum(item.quantity * item.product.price for item in valid_items), 2)

    # 2. Создаем запись о заказе
    new_order = Order(
        user_id=user_id,
        name=order_data.get("name", ""),
        phone=order_data.get("phone", ""),
        city=order_data.get("city", ""),
        address=order_data.get("address", ""),
        comment=order_data.get("comment"),
        total_price=total_price,
        status="Новый",
    )
    session.add(new_order)

    # Получаем ID нового заказа до коммита
    await session.flush()

    # 3. Создаем позиции заказа и списываем остатки со склада
    for cart_item in valid_items:
        cart_item.product.stock -= cart_item.quantity
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price=cart_item.product.price,  # Фиксируем цену на момент покупки
        )
        session.add(order_item)

    # 4. Очищаем корзину пользователя
    await session.execute(delete(Cart).where(Cart.user_id == user_id))

    # 5. Сохраняем всё одной транзакцией
    await session.commit()

    return new_order


async def restore_order_stock(session: AsyncSession, order_id: int) -> None:
    """Возвращает товары из отмененного заказа обратно на склад."""
    result = await session.execute(
        select(OrderItem)
        .options(joinedload(OrderItem.product))
        .where(OrderItem.order_id == order_id)
    )
    items = result.scalars().all()
    for item in items:
        if item.product:
            item.product.stock += item.quantity