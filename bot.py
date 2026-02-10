import logging
import asyncio
import os
import json
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import gspread
from oauth2client.service_account import ServiceAccountCredentials



# ------------------------
# LOGGING
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
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Leads")  # имя таблицы

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

creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
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
# START COMMAND
# ------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("Привет!👋 \n..... \n  \nДля начала,\nКак вас зовут?")
    await state.set_state(LeadForm.waiting_for_name)

# ------------------------
# NAME
# ------------------------
@dp.message(LeadForm.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name.replace(" ", "").isalpha():
        await message.answer("Пожалуйста, введите только имя (только буквы)")
        return
    await state.update_data(name=name)
    await message.answer("Отлично! Теперь пришлите свой номер телефона (только цифры, пример: 79991234567)")
    await state.set_state(LeadForm.waiting_for_phone)

# ------------------------
# PHONE
# ------------------------
@dp.message(LeadForm.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = re.sub(r"\D", "", message.text)  # оставляем только цифры
    if len(phone) < 10 or len(phone) > 15:
        await message.answer("Некорректный номер, введите только цифры, длина 10–15 символов")
        return

    # Проверка дубликатов
    existing_numbers = sheet.col_values(5)  # телефон — 5 колонка
    if phone in existing_numbers:
        await message.answer("Такой номер уже зарегистрирован. Введите другой номер.")
        return

    await state.update_data(phone=phone)
    await message.answer("Что для вас самое важное в жизни?")
    await state.set_state(LeadForm.waiting_for_question)

# ------------------------
# QUESTION + RECORD
# ------------------------
@dp.message(LeadForm.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    question = message.text.strip()
    if not question:
        await message.answer("Пожалуйста, напишите что-то")
        return

    data = await state.get_data()
    date = datetime.now() + timedelta(hours=3).strftime("%d.%m.%Y %H:%M")
    username = message.from_user.username or "Не задан"
    user_id = message.from_user.id

    row = [
        username,
        user_id,
        data["name"],
        date,
        data["phone"],
        question,
        "Новый"
    ]

    try:
        sheet.append_row(row)
        await message.answer("Спасибо! Ваша заявка принята ✅")
        logger.info(f"Лид добавлен: {row}")
    except Exception as e:
        logger.error(f"Ошибка записи в Google Sheet: {e}")
        await message.answer("Произошла ошибка при записи. Попробуйте позже.")

    await state.clear()

# ------------------------
# FALLBACK
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
