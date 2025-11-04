import asyncio
from aiogram import Dispatcher, F, Bot
from aiogram.filters import CommandStart
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



# Создаем главное меню
def create_reply_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Оформить заказ"),
            ],
            [
                KeyboardButton(text="Онлайн-ассистент"),
            ],
            [
                KeyboardButton(text="Обратная связь"),
            ],
        ],
        resize_keyboard=True,
    )


# Определяем состояния для FSM
class FeedbackStates(StatesGroup):
    waiting_for_user_message = State()

class OrderStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_tournament = State()

class AIAssistantStates(StatesGroup):
    waiting_for_question = State()

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
        await message.answer(
        "Добро пожаловать в фотостудию <b>Миг</b>! 📸\n\n"
        "Мы специализируемся на профессиональной фотографии и видеосъемке спортивных мероприятий. "
        "Наша команда поможет запечатлеть самые яркие моменты ваших соревнований и достижений.\n\n"
        "Выберите нужный пункт меню, чтобы оформить заказ или задать вопрос 👇🏻",
        reply_markup=create_reply_menu(),
    )


# Обработчик кнопки "Онлайн-ассистент"
@dp.message(F.text == "Онлайн-ассистент")
async def ai_assistant_handler(message: Message, state: FSMContext):
    await state.clear()  # Clear any existing state
    await state.set_state(AIAssistantStates.waiting_for_question)
    await message.answer(
        "Я - Алина, твой онлайн-ассистент. Можешь задать мне любой вопрос!",
        reply_markup=create_reply_menu()
    )


# Обработчик вопросов для AI ассистента
@dp.message(
    AIAssistantStates.waiting_for_question,
    ~F.text.in_(["Оформить заказ", "Обратная связь", "Онлайн-ассистент"])
)
async def handle_ai_question(message: Message, state: FSMContext):
    
    # Build message history with system prompt
    user_id = message.from_user.id
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Get or initialize user history from state
    user_data = await state.get_data()
    if 'ai_history' not in user_data:
        user_data['ai_history'] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    history = user_data['ai_history']
    
    # Add user question
    history.append({"role": "user", "content": message.text})
    
    try:
        # Get AI response
        processing_msg = await message.answer("⏳ Обрабатываю ваш вопрос...")
        response = await ai_answer(history)
        
        # Add AI response to history
        history.append({"role": "assistant", "content": response})
        
        # Save updated history
        await state.update_data(ai_history=history)
        
        # Send response
        await processing_msg.delete()
        await message.answer(response, reply_markup=create_reply_menu())
        
    except Exception as e:
        logging.error(f"Ошибка в AI ассистенте: {e}")
        await message.answer(
            "Извините, произошла ошибка при обработке вашего вопроса. Попробуйте еще раз позже.",
            reply_markup=create_reply_menu()
        )


# Обработчик кнопки "Оформить заказ"
@dp.message(F.text == "Оформить заказ")
async def order_start(message: Message, state: FSMContext):
    await state.clear()  # Clear any existing state
    await state.set_state(OrderStates.waiting_for_name)
    await message.answer(
        "Для оформления заказа мне нужна информация от вас.\n\n"
        "Пожалуйста, укажите ваше <b>Имя и Фамилию</b>:",
        reply_markup=create_reply_menu()
    )


@dp.message(
    OrderStates.waiting_for_name,
    ~F.text.in_(["Оформить заказ", "Обратная связь", "Онлайн-ассистент"])
)
async def get_order_name(message: Message, state: FSMContext):
    
    await state.update_data(order_name=message.text)
    await state.set_state(OrderStates.waiting_for_tournament)
    await message.answer(
        "Спасибо! Теперь укажите <b>Название турнира</b>:",
        reply_markup=create_reply_menu()
    )


@dp.message(
    OrderStates.waiting_for_tournament,
    ~F.text.in_(["Оформить заказ", "Обратная связь", "Онлайн-ассистент"])
)
async def get_order_tournament(message: Message, state: FSMContext):
    
    user_data = await state.get_data()
    order_name = user_data.get("order_name", "")
    tournament_name = message.text
    
    # Send confirmation to user
    await message.answer(
        "✅ Ваш заказ принят к выполнению!\n\n"
        "Мы свяжемся с вами в ближайшее время. Ожидайте обратной связи от нас.",
        reply_markup=create_reply_menu()
    )
    
    # Send order details to admin
    user_id = message.from_user.id
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


# Обработчики для кнопки "Обратная связь"
@dp.message(F.text == "Обратная связь")
async def feedback_menu(message: Message, state: FSMContext):
    await state.clear()  # Clear any existing state
    feedback_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Написать нам", callback_data="write_us")],
        [InlineKeyboardButton(text="Рассказать другу", callback_data="tell_friend")],
        [InlineKeyboardButton(text="Мы в соц сетях", callback_data="social_networks")],
        [InlineKeyboardButton(text="Посетить наш сайт", url="https://fotomig.net")],
    ])
    await message.answer(
        "Пожалуйста, выберите вариант обратной связи:\n\n",
        reply_markup=feedback_keyboard
    )

@dp.callback_query(F.data == "write_us")
async def write_us(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Напишите свое сообщение ниже, и мы обязательно ответим.")
    await state.set_state(FeedbackStates.waiting_for_user_message)
    await callback.answer()

@dp.message(
    FeedbackStates.waiting_for_user_message,
    ~F.text.in_(["Оформить заказ", "Обратная связь", "Онлайн-ассистент"])
)
async def forward_to_admin(message: Message, state: FSMContext):
    
    if message.from_user.id not in ADMIN_ID:
        user_id = message.from_user.id
        user_name = message.from_user.full_name
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Ответить", callback_data=f"reply_{user_id}")]
            ]
        )
        logging.info(f"Создаю кнопку 'Ответить' для сообщения от {user_name} ({user_id})")
        try:
            # Отправляем сообщение всем администраторам
            for admin_id in ADMIN_ID:
                await bot.send_message(
                    admin_id,
                    f"Новое сообщение от:\n{user_name}\n\n<b>{message.text}</b>",
                    reply_markup=keyboard
                )
        except Exception as e:
            logging.error(f"❌ Ошибка отправки сообщения администратору: {e}")
        await message.answer("✅ Ваше сообщение отправлено администратору.\n\nОжидайте ответа!")
        await state.clear()

@dp.callback_query(F.data.startswith("reply_order_"))
async def ask_admin_reply_order(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(user_id=user_id)
    await state.set_state(AdminReplyState.waiting_for_reply)
    logging.info(f"Администратор нажал 'Ответить на заказ' для пользователя {user_id}.")
    await callback.message.answer(f"Введите ответ для пользователя (ID: `{user_id}`):")
    await callback.answer()

@dp.callback_query(F.data.startswith("reply_"))
async def ask_admin_reply(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    user_name = callback.message.text.split("\n")[1]
    await state.update_data(user_id=user_id)
    await state.set_state(AdminReplyState.waiting_for_reply)
    logging.info(f"Администратор нажал 'Ответить' для {user_id}.")
    await callback.message.answer(f"Введите ответ для пользователя `{user_name}` (id: `{user_id}`):")
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

@dp.callback_query(F.data == "tell_friend")
async def tell_friend(callback: CallbackQuery):
    await callback.message.answer(
        "Поделитесь нашим ботом с друзьями!\n\n"
        "Мы поможем им запечатлеть яркие моменты на спортивных мероприятиях! 📸"
    )
    await callback.answer()

@dp.callback_query(F.data == "social_networks")
async def social_networks(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Instagram", url="https://instagram.com")],
        [InlineKeyboardButton(text="ВКонтакте", url="https://vk.com")],
    ])
    await callback.message.answer(
        "Подписывайтесь на нас в социальных сетях!\n\n"
        "Следите за свежими фото и видео с мероприятий! 📸",
        reply_markup=keyboard
    )
    await callback.answer()

# Обработчик для сообщений вне меню
@dp.message()
async def handle_unknown_message(message: Message):
    await message.answer("Не понял вас.\n\n Пожалуйста, выберите пункт в меню ниже 👇🏻",
                         reply_markup=create_reply_menu())



async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())