import asyncio
from aiogram import Dispatcher, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from mistralai import Mistral
import logging
logging.basicConfig(level=logging.INFO)


from configuration import BOT_TOKEN, API_KEY, MODEL_NAME, ADMIN_ID


# 1. Функция для чтения промпта
def load_system_prompt(filename):
    """Считывает системный промпт из текстового файла."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.error(f"Файл промпта не найден: {filename}")
        return "Ты - полезный ассистент фотостудии Миг." # Запасной (fallback) промпт


# 2. Замените старую переменную SYSTEM_PROMPT на вызов функции
SYSTEM_PROMPT = load_system_prompt('system_prompt.txt')

# Функция для взаимодействия с Mistral AI
async def get_ai_response(content, prompt):
    try:
        client = Mistral(api_key=API_KEY)

        response = await client.chat.stream_async(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
        )
        result = ""
        async for chunk in response:
            delta_content = chunk.data.choices[0].delta.content
            if delta_content:
                result += delta_content
        return result or "Ошибка: Пустой ответ от модели."
    except Exception as e:
        return f"Произошла ошибка: {e}"

async def ai_answer(history: list) -> str:
    """Отправляет историю диалога в Mistral и получает ответ."""
    try:
        client = Mistral(api_key=API_KEY)
        
        # Стриминг ответа (можно и без стриминга, но так надежнее для длинных текстов)
        response = await client.chat.stream_async(
            model=MODEL_NAME,
            messages=history,
        )
        result = ""
        async for chunk in response:
            delta_content = chunk.data.choices[0].delta.content
            if delta_content:
                result += delta_content
        return result or "Извините, я задумался. Повторите вопрос."
    except Exception as e:
        logging.error(f"Ошибка Mistral AI: {e}")
        return "Произошла техническая ошибка. Пожалуйста, напишите нам на почту fotomig33@ya.ru"

# Создаем экземпляры бота и диспетчера ,session=session
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()



# Создаем главное меню (пустое, так как кнопок нет)
def create_reply_menu():
    return ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
    )

# Хранилище истории сообщений для ИИ (в памяти)
ai_history_storage = {}

# Команда /start
@dp.message(CommandStart())
async def start_command(message: Message):
    full_name = message.from_user.full_name
    
    await message.answer(
        f"Здравствуйте, {full_name}! Меня зовут Анна, я ассистент фотостудии Фотомиг.\n\n"
        "Вы ждете заказ с турнира?\n\n"
        "Пожалуйста, напишите сюда ОДНИМ СООБЩЕНИЕМ:\n\n"
        "1. Вашу Фамилию (как в квитанции);\n"
        "2. Название турнира.\n"
        "Пример: Иванова Первенство 2025.\n\n"
        "❌ Не нужно присылать фотографию квитанции ❌\n\n"
        "‼️‼️ Обращаем ваше внимание, что сроки и время отправки указаны внизу на вашей квитанции, пожалуйста, ожидайте ☺️",
    )



# Обработчик для всех сообщений (ИИ отвечает на все, кроме логики оформления заказа)
@dp.message()
async def handle_ai_message(message: Message):
    if not message.text:
        return

    user_id = message.from_user.id
    
    # -- Работа с историей диалога --
    if user_id not in ai_history_storage:
        # Если истории нет, создаем новую с Системным Промптом
        ai_history_storage[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    history = ai_history_storage[user_id]
    
    # Ограничиваем историю (например, последние 20 сообщений), чтобы не тратить токены
    if len(history) > 20:
        # Оставляем системный промпт [0] + последние 10 сообщений
        history = [history[0]] + history[-10:]

    # Добавляем сообщение пользователя
    history.append({"role": "user", "content": message.text})
    
    # -- Получаем ответ от ИИ --
    # Показываем статус "печатает..." для живости
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    ai_response = await ai_answer(history)
    
    # Добавляем ответ бота в историю
    history.append({"role": "assistant", "content": ai_response})
    ai_history_storage[user_id] = history
    
    # Отправляем ответ пользователю
    await message.answer(ai_response)



async def main():
    # Устанавливаем меню команд
    commands = [
        BotCommand(command="start", description="Перезапустить бот"),
    ]
    await bot.set_my_commands(commands)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())