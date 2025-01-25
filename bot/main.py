import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)


@dp.message(F.text == "/start")
async def start_handler(message: Message):
    button = KeyboardButton(text="Получить данные по товару")
    keyboard = ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

    await message.answer(
        "Бот в разработке.", reply_markup=keyboard
    )


if __name__ == "__main__":
    dp.run_polling(bot)
