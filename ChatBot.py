import asyncio
from aiogram import Dispatcher, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from mistralai import Mistral
from db import Database
import logging
logging.basicConfig(level=logging.INFO)

import sqlite3




from configuration import BOT_TOKEN, API_KEY, MODEL_NAME, ADMIN_ID, DATABASE_FILE


# AI Assistant system prompt
SYSTEM_PROMPT = """
Ты - Алина, полезный ассистент фотостудии Миг. Отвечай всегда на русском языке.
Фотостудия Миг - это фотостудия, которая занимается профессиональной фотографией и видеосъемкой спортивных мероприятий.
Отвечай так, чтобы клиентам было комфортно и понятно.
Не упоминай, что ты бот, просто отвечай на вопросы.
"""

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

async def ai_answer(message: list) -> str:
    """Get AI response from Mistral AI"""
    try:
        client = Mistral(api_key=API_KEY)

        response = await client.chat.stream_async(
            model=MODEL_NAME,
            messages=message,
        )
        result = ""
        async for chunk in response:
            delta_content = chunk.data.choices[0].delta.content
            if delta_content:
                result += delta_content
        return result or "Ошибка: Пустой ответ от модели."
    except Exception as e:
        return f"Произошла ошибка: {e}"

# Создаем экземпляры бота и диспетчера ,session=session
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()
db = Database(DATABASE_FILE)



# Создаем главное меню (пустое, так как кнопок нет)
def create_reply_menu():
    return ReplyKeyboardMarkup(
        keyboard=[],
        resize_keyboard=True,
    )

# Хранилище истории сообщений для ИИ (в памяти)
ai_history_storage = {}


# Определяем состояния для FSM
class OrderStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_tournament = State()

class AdminReplyState(StatesGroup):
    waiting_for_reply = State()


# Команда /start
@dp.message(CommandStart())
async def start_command(message: Message):
    if message.chat.type == 'private':
        user_id = message.from_user.id
        full_name = message.from_user.full_name
        if not db.user_exists(user_id):
            db.add_user(user_id, full_name)
        else:
            # Update name if user already exists but name changed
            db.update_user_name(user_id, full_name)
        inline_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Хочу получить свой заказ", callback_data="send_order_data")]
            ]
        )
        await message.answer(
        "✅Ваше сообщение получено✅\n\n"
        "Пожалуйста, убедитесь, что Вы прислали ТЕКСТОМ фамилию, которая написана на вашей квитанции и не забыли про название турнира 😉\n"
        "❌Не нужно присылать фотографию квитанции❌\n\n"
        "‼️‼️Обращаем ваше внимание, что сроки и время отправки указаны внизу на вашей квитанции, пожалуйста, ожидайте ☺️",
        reply_markup=inline_keyboard,
    )




# Обработчик инлайн-кнопки "Хочу получить свой заказ"
@dp.callback_query(F.data == "send_order_data")
async def send_order_data_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # Clear any existing state
    await state.set_state(OrderStates.waiting_for_name)
    cancel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отменить", callback_data="cancel_order")]
        ]
    )
    await callback.message.answer(
        "Для получения заказа мне нужна информация от вас.\n\n"
        "Пожалуйста, укажите ваше <b>Имя и Фамилию</b>:\n\n"
        "Если хотите отменить действие, нажмите <b>Отменить</b>.",
        reply_markup=cancel_keyboard
    )
    await callback.answer()

# Команда /send_info
@dp.message(Command("send_info"))
async def send_info_command(message: Message, state: FSMContext):
    await state.clear()  # Clear any existing state
    await state.set_state(OrderStates.waiting_for_name)
    cancel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отменить", callback_data="cancel_order")]
        ]
    )
    await message.answer(
        "Для получения заказа мне нужна информация от вас.\n\n"
        "Пожалуйста, укажите ваше <b>Имя и Фамилию</b>:\n\n"
        "Если хотите отменить действие, нажмите <b>Отменить</b>.",
        reply_markup=cancel_keyboard
    )


@dp.message(OrderStates.waiting_for_name, ~F.text.startswith("/"))
async def get_order_name(message: Message, state: FSMContext):
    
    await state.update_data(order_name=message.text)
    await state.set_state(OrderStates.waiting_for_tournament)
    back_cancel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Назад", callback_data="back_to_name"),
                InlineKeyboardButton(text="Отменить", callback_data="cancel_order")
            ]
        ]
    )
    await message.answer(
        "Спасибо! Теперь укажите <b>Название турнира</b>:\n\n"
        "Если хотите вернуться назад, нажмите <b>Назад</b>. Если хотите отменить действие, нажмите <b>Отменить</b>.",
        reply_markup=back_cancel_keyboard
    )


# Обработчик кнопки "Отменить"
@dp.callback_query(F.data == "cancel_order")
async def cancel_order_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    send_data_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Хочу получить свой заказ", callback_data="send_order_data")]
        ]
    )
    await callback.message.answer(
        "❌ Отменено.\n\n"
        "Если передумали, можно снова отправить нам данные.",
        reply_markup=send_data_keyboard
    )
    await callback.answer("Заказ отменен")

# Обработчик кнопки "Назад"
@dp.callback_query(F.data == "back_to_name")
async def back_to_name_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_name)
    cancel_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отменить", callback_data="cancel_order")]
        ]
    )
    await callback.message.answer(
        "Для получения заказа мне нужна информация от вас.\n\n"
        "Пожалуйста, укажите ваше <b>Имя и Фамилию</b>:\n\n"
        "Если хотите отменить действие, нажмите <b>Отменить</b>.",
        reply_markup=cancel_keyboard
    )
    await callback.answer()

@dp.message(OrderStates.waiting_for_tournament, ~F.text.startswith("/"))
async def get_order_tournament(message: Message, state: FSMContext):
    
    user_data = await state.get_data()
    order_name = user_data.get("order_name", "")
    tournament_name = message.text
    
    # Сохраняем заказ в базу данных
    user_id = message.from_user.id
    try:
        db.add_order(user_id, order_name, tournament_name)
        logging.info(f"Заказ сохранен в БД для пользователя {user_id}")
    except Exception as e:
        logging.error(f"Ошибка сохранения заказа в БД: {e}")
    
    # Send confirmation to user
    send_data_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Хочу получить свой заказ", callback_data="send_order_data")]
        ]
    )
    await message.answer(
        "✅ Информация получена!\n\n"
        "Мы свяжемся с вами в ближайшее время. Ожидайте обратной связи от нас.\n\n"
        "Если хотите получить еще один заказ, то нажмите на кнопку ниже.",
        reply_markup=send_data_keyboard
    )
    
    # Send order details to admin
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ответить на заказ", callback_data=f"reply_order_{user_id}")]
        ]
    )
    
    admin_message = (
        f"🎯 <b>Новый заказ</b>\n\n"
        f"<b>Имя и Фамилия:</b> {order_name}\n"
        f"<b>Название турнира:</b> {tournament_name}\n"
        f"<b>ID пользователя:</b> {user_id}\n"
        f"<b>Username:</b> @{message.from_user.username if message.from_user.username else 'нет'}"
    )
    
    try:
        # Отправляем сообщение всем администраторам
        for admin_id in ADMIN_ID:
            await bot.send_message(admin_id, admin_message, reply_markup=keyboard)
    except Exception as e:
        logging.error(f"❌ Ошибка отправки заказа администратору: {e}")
    await state.clear()


@dp.callback_query(F.data.startswith("reply_order_"))
async def ask_admin_reply_order(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(user_id=user_id)
    await state.set_state(AdminReplyState.waiting_for_reply)
    logging.info(f"Администратор нажал 'Ответить на заказ' для пользователя {user_id}.")
    await callback.message.answer(f"Введите ответ для пользователя (ID: `{user_id}`):")
    await callback.answer()

@dp.message(AdminReplyState.waiting_for_reply)
async def send_admin_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя для ответа.")
        return
    try:
        await bot.send_message(user_id, f"📢 Ответ от администратора:\n\n{message.text}")
        await message.answer(f"✅ Ответ успешно отправлен пользователю c id `{user_id}`.")
        logging.info(f"✅ Ответ администратора отправлен пользователю {user_id}.")
    except Exception as e:
        logging.error(f"❌ Ошибка отправки ответа пользователю {user_id}: {e}")
        await message.answer(f"❌ Ошибка при отправке сообщения пользователю: {str(e)}")
    await state.clear()

# Обработчик для всех сообщений (ИИ отвечает на все, кроме логики оформления заказа)
@dp.message()
async def handle_ai_message(message: Message, state: FSMContext):
    # Проверяем, не находится ли пользователь в процессе оформления заказа или ответа админа
    current_state = await state.get_state()
    if current_state in [OrderStates.waiting_for_name, OrderStates.waiting_for_tournament, AdminReplyState.waiting_for_reply]:
        # Если пользователь в процессе оформления заказа или админ отвечает, не обрабатываем через ИИ
        return
    
    # Проверяем, что сообщение содержит текст
    if not message.text:
        # Если сообщение не текстовое, просим отправить текст
        await message.answer(
            "Пожалуйста, отправьте текстовое сообщение. Я могу отвечать только на текстовые сообщения.",
            reply_markup=create_reply_menu()
        )
        return
    
    # Получаем или инициализируем историю для пользователя
    user_id = message.from_user.id
    if user_id not in ai_history_storage:
        ai_history_storage[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    history = ai_history_storage[user_id]
    
    # Получаем информацию о заказах пользователя и добавляем в контекст
    try:
        user_orders = db.get_user_orders(user_id)
        if user_orders:
            orders_info = "\n\nВаши заказы:\n"
            for order in user_orders:
                order_id, order_name, tournament_name, created_at = order
                orders_info += f"- Заказ #{order_id}: {order_name}, Турнир: {tournament_name}, Дата: {created_at}\n"
            
            # Всегда обновляем системный промпт с актуальной информацией о заказах
            enhanced_system_prompt = SYSTEM_PROMPT + orders_info
            # Обновляем системный промпт в истории
            if len(history) > 0 and history[0]["role"] == "system":
                history[0] = {"role": "system", "content": enhanced_system_prompt}
            else:
                # Если системного промпта еще нет, добавляем его
                history.insert(0, {"role": "system", "content": enhanced_system_prompt})
        else:
            # Если заказов нет, просто используем базовый системный промпт
            if len(history) == 0 or history[0]["role"] != "system":
                history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    except Exception as e:
        logging.error(f"Ошибка получения заказов пользователя для ИИ: {e}")
        # В случае ошибки используем базовый промпт
        if len(history) == 0 or history[0]["role"] != "system":
            history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    
    # Добавляем сообщение пользователя
    history.append({"role": "user", "content": message.text})
    
    try:
        # Получаем ответ от ИИ
        response = await ai_answer(history)
        
        # Добавляем ответ ИИ в историю
        history.append({"role": "assistant", "content": response})
        
        # Обновляем историю
        ai_history_storage[user_id] = history
        
        # Отправляем ответ
        await message.answer(response, reply_markup=create_reply_menu())
        
    except Exception as e:
        logging.error(f"Ошибка в AI ассистенте: {e}")
        await message.answer(
            "Извините, произошла ошибка при обработке вашего вопроса. Попробуйте еще раз позже.",
            reply_markup=create_reply_menu()
        )



async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())