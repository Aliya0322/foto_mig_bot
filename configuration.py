import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Получаем конфигурацию из переменных окружения
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "codestral-latest")
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
# Извлекаем путь к файлу БД из DATABASE_URL или используем дефолтное значение
if DATABASE_URL and DATABASE_URL.startswith("sqlite:///"):
    DATABASE_FILE = DATABASE_URL.replace("sqlite:///", "")
elif DATABASE_URL:
    DATABASE_FILE = DATABASE_URL
else:
    DATABASE_FILE = os.getenv("DATABASE_FILE", "foto_mig_bot.db")
# ADMIN_ID может содержать несколько ID через запятую
ADMIN_IDS_STR = os.getenv("ADMIN_ID", "")
ADMIN_ID = [int(id.strip()) for id in ADMIN_IDS_STR.split(",") if id.strip()]

# Другие настройки
user_requests = {}