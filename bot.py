import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import Database
from modules.account_manager import AccountManager
from modules.task_manager import TaskManager
from keyboards import main_menu_kb
from handlers import (
    accounts_handlers,
    tasks_handlers,
    actions_handlers,
    templates_handlers
)

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# База данных и менеджеры
db = Database()
account_manager = AccountManager(db)
task_manager = TaskManager(db, account_manager)

# Передаем зависимости в роутеры
accounts_handlers.setup(db, account_manager)
tasks_handlers.setup(db, task_manager)
actions_handlers.setup(db, account_manager, task_manager)
templates_handlers.setup(db)

# === ОСНОВНЫЕ ОБРАБОТЧИКИ ===

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Проверка на админа
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("У вас нет доступа к этому боту.")
        return

    # Отправляем стикер приветствия, если он указан
    if config.WELCOME_STICKER_ID:
        try:
            await message.answer_sticker(config.WELCOME_STICKER_ID)
        except Exception as e:
            logger.error(f"Ошибка отправки стикера: {e}")

    # Приветственное сообщение
    welcome_text = """
🤖 <b>Добро пожаловать в бот управления аккаунтами!</b>

Этот бот позволяет управлять множеством Telegram аккаунтов для выполнения различных задач:

📱 <b>Функции бота:</b>
• Массовый вход/выход из групп
• Отправка скриншот-уведомлений
• Массовая рассылка сообщений
• Участие в голосовых чатах
• Установка реакций
• Подписка на каналы
• Запуск ботов по реферальным ссылкам
• Очистка аккаунтов

⚡ <b>Возможности управления:</b>
• Добавление новых аккаунтов
• Мониторинг состояния аккаунтов
• Управление сессиями
• Отслеживание задач
• Шаблоны сообщений

Выберите действие из меню ниже:
"""

    await message.answer(
        welcome_text,
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "menu_main")
async def menu_main(callback: CallbackQuery):
    """Главное меню"""
    text = "🏠 <b>Главное меню</b>\n\nВыберите раздел:"

    await callback.message.edit_text(
        text,
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "menu_settings")
async def menu_settings(callback: CallbackQuery):
    """Настройки"""
    from keyboards import settings_menu_kb

    settings_text = """
⚙️ <b>Настройки</b>

Управление конфигурацией бота.
"""

    await callback.message.edit_text(
        settings_text,
        reply_markup=settings_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "settings_general")
async def settings_general(callback: CallbackQuery):
    """Общие настройки"""
    from keyboards import back_button

    general_settings_text = """
🔧 <b>Общие настройки</b>

<b>Текущая конфигурация:</b>
• API ID: настроен
• API Hash: настроен
• Папка сессий: sessions/
• База данных: bot.db

<i>Для изменения настроек отредактируйте файл config.py</i>
"""

    await callback.message.edit_text(
        general_settings_text,
        reply_markup=back_button("menu_settings"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "menu_help")
async def menu_help(callback: CallbackQuery):
    """Помощь"""
    from keyboards import back_button

    help_text = """
📖 <b>Помощь</b>

<b>Основные разделы:</b>

📱 <b>Аккаунты</b>
Управление телеграм-аккаунтами: добавление, удаление, проверка состояния, управление сессиями.

⚡ <b>Задачи</b>
Мониторинг запущенных и завершенных задач. Возможность остановки всех задач.

🚀 <b>Запустить действие</b>
Выполнение различных действий с аккаунтами: рассылки, вход в группы, реакции и т.д.

📝 <b>Шаблоны</b>
Создание и управление шаблонами сообщений для рассылок.

<b>Как начать?</b>
1. Добавьте аккаунты через раздел "Аккаунты"
2. Создайте шаблоны сообщений (если нужно)
3. Выберите действие и следуйте инструкциям
4. Отслеживайте выполнение в разделе "Задачи"

<b>Важно:</b>
• Не перегружайте аккаунты задачами
• Следите за флуд-контролем Telegram
• Используйте задержки между действиями
• Регулярно проверяйте состояние аккаунтов
"""

    await callback.message.edit_text(
        help_text,
        reply_markup=back_button("menu_main"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """Пустой callback для информационных кнопок"""
    await callback.answer()

# === ЗАПУСК БОТА ===

async def on_startup():
    """Действия при запуске"""
    logger.info("Инициализация базы данных...")
    await db.init_db()
    logger.info("Бот запущен!")

async def on_shutdown():
    """Действия при остановке"""
    logger.info("Остановка всех задач...")
    await task_manager.stop_all_tasks()
    logger.info("Отключение всех аккаунтов...")
    await account_manager.disconnect_all()
    logger.info("Бот остановлен!")

async def main():
    """Главная функция"""
    # Подключаем роутеры
    dp.include_router(accounts_handlers.router)
    dp.include_router(tasks_handlers.router)
    dp.include_router(actions_handlers.router)
    dp.include_router(templates_handlers.router)

    # Запускаем
    await on_startup()

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем")
