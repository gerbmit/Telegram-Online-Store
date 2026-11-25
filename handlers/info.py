from aiogram import Router, F
from aiogram.types import Message
from utils.texts import Buttons, Messages

info_router = Router()

@info_router.message(F.text == Buttons.PROMO)
async def show_promo(message: Message):
    """Обработчик кнопки 'Акции'"""
    await message.answer(Messages.PROMO_TEXT)

@info_router.message(F.text == Buttons.ABOUT)
async def show_about(message: Message):
    """Обработчик кнопки 'О магазине'"""
    await message.answer(Messages.ABOUT_TEXT)