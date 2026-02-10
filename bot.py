import logging
import asyncio
import os
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ------------------------
# ЛОГИ
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ------------------------
# TELEGRAM TOKEN (Railway Variable)
# ------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ------------------------
# GOOGLE SHEETS (Railway Variable)
# ------------------------
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
GOOGLE_SHEET_NAME = "Leads"  # ← имя таблицы

if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("❌ GOOGLE_CREDENTIALS_JSON не задан")

try:
    google_creds = json.loads(GOOGLE_CREDENTIALS_JSON)
except json.JSONDecodeError as e:
    raise RuntimeError("❌ GOOGLE_CREDENTIALS_JSON — невалидный JSON") from e

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    google_creds, scope
)

gc = gspread.authorize(creds)
sheet = gc.open(GOOGLE_SHEET_NAME).sheet1


# ------------------------
# FSM
# ------------------------
class LeadForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_question = State()


# ------------------------
# /start
# ------------------------
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"Новый пользователь: {message.from_user.id}")
    await message.answer("Привет! 👋 Я помогу оставить заявку.")
    await message.answer("Сначала скажи, как тебя зовут?")
    await state.set_state(LeadForm.waiting_for_name)


# ------------------------
# Имя
# ------------------------
@dp.message(LeadForm.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Отлично! Теперь пришли свой телефон.")
    await state.set_state(LeadForm.waiting_for_phone)


# ------------------------
# Телефон
# ------------------------
@dp.message(LeadForm.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("И последний вопрос: есть ли уточнение или комментарий?")
    await state.set_state(LeadForm.waiting_for_question)


# ------------------------
# Вопрос + запись в Google Sheets
# ------------------------
@dp.message(LeadForm.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text)
    data = await state.get_data()

    date = datetime.now().strftime("%d.%m.%Y %H:%M")
    row = [
        date,
        data["name"],
        data["phone"],
        data["question"],
        "Новый"
    ]

    try:
        sheet.append_row(row)
        await message.answer("Спасибо! Ваша заявка принята ✅")
        logger.info(f"Лид добавлен: {row}")
    except Exception as e:
        logger.error(f"Ошибка записи в Google Sheet: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

    await state.clear()


# ------------------------
# Фоллбэк
# ------------------------
@dp.message()
async def fallback(message: types.Message):
    await message.answer("Чтобы оставить заявку, напишите /start")


# ------------------------
# START
# ------------------------
async def main():
    logger.info("🚀 Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
