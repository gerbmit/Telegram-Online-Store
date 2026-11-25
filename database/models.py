from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class User(Base):
    """Модель пользователя Telegram."""
    __tablename__ = "users"

    # В качестве ID используем Telegram ID, поэтому BigInteger
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Связи с другими таблицами
    orders: Mapped[List["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    cart_items: Mapped[List["Cart"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    """Модель категории товаров."""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    products: Mapped[List["Product"]] = relationship(back_populates="category")


class Product(Base):
    """Модель товара."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    old_price: Mapped[Optional[float]] = mapped_column(Float)
    discount: Mapped[int] = mapped_column(Integer, default=0)
    article: Mapped[Optional[str]] = mapped_column(String(50))
    stock: Mapped[int] = mapped_column(Integer, default=0)
    # Храним file_id фотографии из Telegram, чтобы отправлять без задержек
    photo: Mapped[Optional[str]] = mapped_column(String(255))

    category: Mapped["Category"] = relationship(back_populates="products")
    # При удалении товара автоматически чистим его из корзин и избранного
    cart_items: Mapped[List["Cart"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    favorites: Mapped[List["Favorite"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    # В истории заказов оставляем позиции, обнуляя ссылку на удаленный товар
    order_items: Mapped[List["OrderItem"]] = relationship(back_populates="product")


class Order(Base):
    """Модель заказа."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(255))
    comment: Mapped[Optional[str]] = mapped_column(Text)

    total_price: Mapped[float] = mapped_column(Float)
    # Статусы: 'Новый', 'Оплачен', 'Отправлен', 'Завершен', 'Отменен'
    status: Mapped[str] = mapped_column(String(50), default="Новый")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Товары внутри конкретного заказа."""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )

    quantity: Mapped[int] = mapped_column(Integer)
    # Фиксируем цену на момент покупки, чтобы при изменении цены товара сумма старого заказа не съехала
    price: Mapped[float] = mapped_column(Float)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="order_items")


class Cart(Base):
    """Корзина пользователя."""
    __tablename__ = "cart"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship(back_populates="cart_items")
    product: Mapped["Product"] = relationship(back_populates="cart_items")


class Favorite(Base):
    """Избранные товары."""
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    user: Mapped["User"] = relationship(back_populates="favorites")
    product: Mapped["Product"] = relationship(back_populates="favorites")