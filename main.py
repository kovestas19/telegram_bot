import os
import sqlite3
import requests
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

load_dotenv()
# Инициализация бота


API_TOKEN = os.getenv('API_TOKEN')
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

DATABASE_NAME = os.path.join('app_data', 'rates_bot.db')


import requests
import xml.etree.ElementTree as ET
from datetime import datetime


# Создание/открытие базы данных
def create_db():
    if not os.path.exists('app_data'):
        os.makedirs('app_data')

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rates_bot (
            currency_from TEXT,
            currency_to TEXT,
            rate REAL,
            spread REAL,
            final_rate REAL,
            is_active BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

create_db()

def fetch_and_store_exchange_rates():
    # Формирование даты для запроса
    date = datetime.now().strftime("%d/%m/%Y")
    url = f'http://www.cbr.ru/scripts/XML_daily.asp?date_req={date}'

    # Получение и парсинг XML
    response = requests.get(url)
    tree = ET.fromstring(response.content)

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Удаление старых курсов
    cursor.execute('DELETE FROM rates_bot')

    # Чтение и сохранение новых курсов
    for valute in tree.findall('Valute'):
        char_code = valute.find('CharCode').text
        nominal = float(valute.find('Nominal').text.replace(',', '.'))
        rate = float(valute.find('Value').text.replace(',', '.'))

        cursor.execute('''
            INSERT INTO rates_bot (currency_from, currency_to, rate, spread, final_rate, is_active)
            VALUES (?, 'RUB', ?, 0.0, ?, 1)
        ''', (char_code, rate/nominal, rate/nominal))
    
    conn.commit()
    conn.close()

# Вызов функции (можно вызвать при старте бота или запланировать задачу)
fetch_and_store_exchange_rates()



@dp.message_handler(commands=['check_all_rates'])
async def check_all_rates(message: types.Message):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT currency_from, rate, final_rate FROM rates_bot WHERE is_active=1
    ''')
    rates = cursor.fetchall()
    conn.close()
    
    if not rates:
        await message.answer("Курсы валют в данный момент недоступны.")
    else:
        response = "Доступные курсы валют:\n"
        response += "\n".join(f"{currency_from} to RUB - Биржевой курс: {rate}, Итоговый курс: {final_rate}" for currency_from, rate, final_rate in rates)
        await message.answer(response)




# Функция для запроса курса
@dp.message_handler(commands=['check_rate'])
async def check_rate(message: types.Message):
    args = message.get_args().split('-')
    if len(args) != 2:
        await message.answer("Пожалуйста, введите запрос в формате 'USD-RUB'.")
    else:
        currency_from, currency_to = args
        await show_rate(message, currency_from, currency_to)

async def show_rate(message, currency_from, currency_to):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rate, spread, final_rate FROM rates_bot
        WHERE currency_from=? AND currency_to=? AND is_active=1
    ''', (currency_from, currency_to))
    rate_info = cursor.fetchone()
    conn.close()
    
    if rate_info:
        rate, spread, final_rate = rate_info
        reply_text = f"Курс биржи: {rate}, Спред: {spread}%, Итоговый курс: {final_rate}"
    else:
        reply_text = "Курс для указанной пары валют не найден или он неактивен."
    await message.answer(reply_text)

# Функция для изменения спреда
@dp.message_handler(commands=['change_spread'])
async def change_spread(message: types.Message):
    # Получаем в аргументах пару валют и желаемый спред
    args = message.get_args().split()
    if len(args) != 2:
        await message.answer("Используйте команду в формате '<FROM-TO> новый_спред', например 'USD-RUB 1.5'.")
    else:
        pair, new_spread = args
        currency_from, currency_to = pair.split('-')
        await update_spread(message, currency_from, currency_to, float(new_spread))

async def update_spread(message: types.Message, currency_from: str, currency_to: str, new_spread: float):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    # Сначала обновляем спред
    cursor.execute('''
        UPDATE rates_bot SET spread=?
        WHERE currency_from=? AND currency_to=?
    ''', (new_spread, currency_from, currency_to))
    conn.commit()
    # Затем обновляем итоговый курс
    cursor.execute('''
        UPDATE rates_bot SET final_rate=rate + rate * (spread / 100.0)
        WHERE currency_from=? AND currency_to=?
    ''', (currency_from, currency_to))
    conn.commit()
    conn.close()
    await message.answer("Спред успешно изменен.")
    # Дополнительная функция для отображения текущего курса
    await show_rate(message, currency_from, currency_to)

# Главное меню
main_menu_kb = ReplyKeyboardMarkup(resize_keyboard=True).add(
    KeyboardButton("/check_rate"),
    KeyboardButton("/change_spread"),
    KeyboardButton("/check_all_rates"),
    KeyboardButton("/home")
)


@dp.message_handler(commands=['home'])
async def home(message: types.Message):
    await message.answer("Добро пожаловать в главное меню.", reply_markup=main_menu_kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)