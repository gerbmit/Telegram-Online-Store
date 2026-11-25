# keyboards/inline.py
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from utils.texts import Buttons

# --- Классы для Callback Data ---

class CategoryCallback(CallbackData, prefix="cat"):
    category_id: int

class ProductCallback(CallbackData, prefix="prod"):
    product_id: int
    action: str  
    quantity: int = 1

class CartCallback(CallbackData, prefix="cart"):
    action: str  
    product_id: int = 0

class ConfirmCallback(CallbackData, prefix="confirm"):
    action: str 

class SupportCallback(CallbackData, prefix="sup"):
    user_id: int

class AdminCategoryCallback(CallbackData, prefix="acat"):
    category_id: int

class AdminManageCatCallback(CallbackData, prefix="mng_cat"):
    action: str 

class AdminDeleteCatCallback(CallbackData, prefix="del_cat"):
    category_id: int

class AdminOrderFilterCallback(CallbackData, prefix="ord_flt"):
    status: str

class AdminOrderStatusCallback(CallbackData, prefix="ord_st"):
    order_id: int
    status: str

class AdminProductManageCallback(CallbackData, prefix="adm_prod"):
    action: str
    product_id: int

# --- Функции генерации клавиатур ---

def get_categories_kb(categories: list) -> InlineKeyboardMarkup:
    # Формирует клавиатуру со списком категорий
    builder = InlineKeyboardBuilder()
    
    for category in categories:
        builder.button(
            text=category.name,
            callback_data=CategoryCallback(category_id=category.id)
        )
    
    builder.adjust(2)
    return builder.as_markup()

def get_products_list_kb(products: list) -> InlineKeyboardMarkup:
    # Формирует клавиатуру со списком товаров
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(
            text=product.title,
            callback_data=ProductCallback(product_id=product.id, action="view")
        )
    
    builder.button(text=Buttons.BACK, callback_data="back_to_catalog")
    builder.adjust(1)
    return builder.as_markup()

def get_product_kb(product_id: int, current_qty: int = 1, in_favorites: bool = False) -> InlineKeyboardMarkup:
    # Клавиатура карточки товара
    builder = InlineKeyboardBuilder()
    
    fav_text = Buttons.REMOVE_FROM_FAV if in_favorites else Buttons.ADD_TO_FAV
    builder.button(text=fav_text, callback_data=ProductCallback(product_id=product_id, action="fav", quantity=current_qty))
    
    builder.button(text=Buttons.MINUS, callback_data=ProductCallback(product_id=product_id, action="minus", quantity=current_qty))
    builder.button(text=str(current_qty), callback_data="ignore") 
    builder.button(text=Buttons.PLUS, callback_data=ProductCallback(product_id=product_id, action="plus", quantity=current_qty))
    
    builder.button(text=Buttons.ADD_TO_CART, callback_data=ProductCallback(product_id=product_id, action="add_cart", quantity=current_qty))
    builder.button(text=Buttons.BACK, callback_data="back_to_catalog")
    
    builder.adjust(1, 3, 1, 1)
    return builder.as_markup()

def get_cart_kb() -> InlineKeyboardMarkup:
    # Клавиатура действий в корзине
    builder = InlineKeyboardBuilder()
    builder.button(text=Buttons.CHECKOUT, callback_data=CartCallback(action="checkout"))
    builder.button(text=Buttons.CLEAR_CART, callback_data=CartCallback(action="clear"))
    
    builder.adjust(1)
    return builder.as_markup()

def get_confirm_kb() -> InlineKeyboardMarkup:
    # Клавиатура подтверждения заказа
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=ConfirmCallback(action="yes"))
    builder.button(text="❌ Отменить", callback_data=ConfirmCallback(action="no"))
    builder.adjust(2)
    return builder.as_markup()

def get_support_reply_kb(user_id: int) -> InlineKeyboardMarkup:
    # Клавиатура для ответа поддержки
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Ответить", callback_data=SupportCallback(user_id=user_id))
    return builder.as_markup()

def get_admin_categories_kb(categories: list) -> InlineKeyboardMarkup:
    # Клавиатура со списком категорий для привязки товара
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.name,
            callback_data=AdminCategoryCallback(category_id=category.id)
        )
    builder.adjust(2)
    return builder.as_markup()

def get_admin_manage_categories_kb(categories: list = None) -> InlineKeyboardMarkup:
    # Клавиатура управления категориями
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить категорию", callback_data=AdminManageCatCallback(action="add"))
    
    if categories:
        for cat in categories:
            builder.button(text=f"❌ Удалить: {cat.name}", callback_data=AdminDeleteCatCallback(category_id=cat.id))
            
    builder.adjust(1)
    return builder.as_markup()

def get_admin_order_filters_kb() -> InlineKeyboardMarkup:
    # Клавиатура фильтрации заказов
    builder = InlineKeyboardBuilder()
    statuses = ["Новый", "Оплачен", "Отправлен", "Завершен", "Отменен"]
    for st in statuses:
        builder.button(text=st, callback_data=AdminOrderFilterCallback(status=st))
    builder.adjust(2)
    return builder.as_markup()

def get_admin_order_status_kb(order_id: int) -> InlineKeyboardMarkup:
    # Клавиатура изменения статуса заказа
    builder = InlineKeyboardBuilder()
    statuses = ["Оплачен", "Отправлен", "Завершен", "Отменен"]
    for st in statuses:
        builder.button(text=f"В '{st}'", callback_data=AdminOrderStatusCallback(order_id=order_id, status=st))
    builder.adjust(2)
    return builder.as_markup()

def get_admin_products_kb(products: list) -> InlineKeyboardMarkup:
    # Клавиатура списка товаров для удаления
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(
            text=f"❌ Удалить: {product.title}",
            callback_data=AdminProductManageCallback(action="delete", product_id=product.id)
        )
    builder.adjust(1)
    return builder.as_markup()