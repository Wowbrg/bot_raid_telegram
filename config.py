import os
from dotenv import load_dotenv

load_dotenv()

# Управляющий бот
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# API для юзерботов
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")

# Стикер приветствия
WELCOME_STICKER_ID = os.getenv("WELCOME_STICKER_ID")

# Пути
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_data.db")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "sessions")
AUDIO_DIR = os.getenv("AUDIO_DIR", "audio")

# Создаем папки если их нет
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

# Настройки
MAX_ACCOUNTS_PER_PAGE = 5  # Количество аккаунтов на странице
TASK_CHECK_INTERVAL = 5  # Интервал проверки задач в секундах
