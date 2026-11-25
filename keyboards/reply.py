# keyboards/reply.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils.texts import Buttons

def get_main_menu() -> ReplyKeyboardMarkup:
    """
    Создает и возвращает главную Reply-клавиатуру.
    resize_keyboard=True делает кнопки компактными (подстраивает под размер экрана).
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Buttons.CATALOG), KeyboardButton(text=Buttons.PROMO)],
            [KeyboardButton(text=Buttons.CART), KeyboardButton(text=Buttons.ORDERS)],
            [KeyboardButton(text=Buttons.PROFILE), KeyboardButton(text=Buttons.FAVORITES)],
            [KeyboardButton(text=Buttons.SUPPORT), KeyboardButton(text=Buttons.ABOUT)]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_menu() -> ReplyKeyboardMarkup:
    """Главное меню администратора."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Buttons.ADMIN_ADD_PRODUCT), KeyboardButton(text=Buttons.ADMIN_PRODUCTS)],
            [KeyboardButton(text=Buttons.ADMIN_CATEGORIES), KeyboardButton(text=Buttons.ADMIN_ORDERS)],
            [KeyboardButton(text=Buttons.ADMIN_BROADCAST), KeyboardButton(text=Buttons.ADMIN_STATS)],
            [KeyboardButton(text=Buttons.ADMIN_EXIT)]
        ],
        resize_keyboard=True
    )
    return keyboard