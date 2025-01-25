import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters.command import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import logging
import httpx

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)


class FSMGetProduct(StatesGroup):
    artikul = State()


@dp.message(CommandStart())
async def start_handler(message: Message):
    keyboard = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Получить данные по товару")],
        [KeyboardButton(text="Инфо")]
    ], resize_keyboard=True)

    await message.answer(
        "Выберите действие.", reply_markup=keyboard
    )


@dp.message(F.text == "Получить данные по товару")
async def get_init_handler(message: Message, state: FSMContext):
    await message.answer("Введите артикул товара")
    await state.set_state(FSMGetProduct.artikul)


@dp.message(FSMGetProduct.artikul)
async def get_product(message: Message, state: FSMContext):
    await state.clear()

    try:
        artikul = int(message.text)
    except ValueError:
        await message.answer("Артикул должен быть целым числом.")
        await start_handler(message)
        return

    async with httpx.AsyncClient() as client:
        url = "http://localhost:8000/api/v1/products"
        payload = {"artikul": artikul}
        response = await client.post(url, json=payload)
        if response.status_code == 200:
            product = response.json()["product"]
            logging.info(product)
            dt_formatted = datetime.fromisoformat(product['last_updated']).strftime('%d-%m-%Y, %H:%M').capitalize()
            await message.answer(f"*Название товара:* {product['name']}\n\n"
                                 f"*Артикул:* `{product['artikul']}`\n"
                                 f"*Цена:* {product['price'] / 100:.2f} ₽\n"
                                 f"*Рейтинг:* {product['rating']}★\n"
                                 f"*В наличии:* {product['stock']} шт.\n"
                                 f"*Обновлено:* {dt_formatted} UTC",
                                 parse_mode="Markdown")
        else:
            await message.answer("Не удалось получить данные о товаре.")


if __name__ == "__main__":
    dp.run_polling(bot)
