import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ------------------------
# Настройка логирования
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------
# Токен бота
# ------------------------
import os
BOT_TOKEN = os.getenv("BOT_TOKEN") # <- вставь сюда токен
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ------------------------
# Подключение к Google Sheet
# ------------------------
GOOGLE_JSON_FILE = "telegramleadbot-486910-465337cabc82.json"  # <- JSON Service Account
GOOGLE_SHEET_NAME = "Leads"           # <- имя таблицы

scope = ["https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"]

import json
from oauth2client.service_account import ServiceAccountCredentials

google_creds = json.loads(os.getenv("GOOGLE_CREDENTIALS"))

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    google_creds, scope
)


gc = gspread.authorize(creds)
sheet = gc.open(GOOGLE_SHEET_NAME).sheet1

# ------------------------
# FSM для сбора данных
# ------------------------
class LeadForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_question = State()

# ------------------------
# /start — микро-прогрев и сбор имени
# ------------------------
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message, state: FSMContext):
    logger.info(f"Новый пользователь: {message.from_user.id}")
    # Микро-прогрев
    await message.answer("Привет! 👋 Я помогу оставить заявку.")
    await message.answer("Сначала скажи, как тебя зовут?")
    await state.set_state(LeadForm.waiting_for_name)

# ------------------------
# Сбор имени
# ------------------------
@dp.message(LeadForm.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    logger.info(f"Имя: {message.text}")
    await message.answer("Отлично! Теперь пришли свой телефон.")
    await state.set_state(LeadForm.waiting_for_phone)

# ------------------------
# Сбор телефона
# ------------------------
@dp.message(LeadForm.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    logger.info(f"Телефон: {message.text}")
    await message.answer("Отлично! И последний вопрос: есть ли уточнение или комментарий?")
    await state.set_state(LeadForm.waiting_for_question)

# ------------------------
# Сбор доп. вопроса и запись в Google Sheet
# ------------------------
@dp.message(LeadForm.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    await state.update_data(question=message.text)
    user_data = await state.get_data()
    name = user_data['name']
    phone = user_data['phone']
    question = user_data['question']
    date = datetime.now().strftime("%d.%m.%Y %H:%M")
    status = "Новый"

    # Запись в Google Sheet
    try:
        sheet.append_row([date, name, phone, question, status])
        await message.answer("Спасибо! Ваша заявка принята ✅")
        logger.info(f"Лид добавлен: {name}, {phone}, {question}")
    except Exception as e:
        logger.error(f"Ошибка записи в Google Sheet: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

    await state.clear()

# ------------------------
# Фоллбэк на любые другие сообщения
# ------------------------
@dp.message()
async def fallback(message: types.Message):
    await message.answer("Чтобы оставить заявку, напишите /start")

# ------------------------
# Запуск бота
# ------------------------
async def main():
    logger.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
