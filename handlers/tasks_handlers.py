from aiogram import Router, F
from aiogram.types import CallbackQuery
import json

from keyboards import tasks_menu_kb, task_detail_kb, back_button
from database import Database
from modules.task_manager import TaskManager

router = Router()

# Глобальные переменные
db: Database = None
task_manager: TaskManager = None

def setup(database: Database, tm: TaskManager):
    """Настройка зависимостей"""
    global db, task_manager
    db = database
    task_manager = tm

# === МЕНЮ ЗАДАЧ ===

@router.callback_query(F.data == "menu_tasks")
async def menu_tasks(callback: CallbackQuery):
    """Меню задач"""
    active_tasks = await db.get_active_tasks()

    text = f"""
⚡ <b>Управление задачами</b>

📊 Активных задач: {len(active_tasks)}

Выберите действие:
"""

    await callback.message.edit_text(
        text,
        reply_markup=tasks_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

# === АКТИВНЫЕ ЗАДАЧИ ===

@router.callback_query(F.data == "tasks_active")
async def tasks_active(callback: CallbackQuery):
    """Список активных задач"""
    tasks = await db.get_active_tasks()

    if not tasks:
        await callback.message.edit_text(
            "📋 Нет активных задач.",
            reply_markup=back_button("menu_tasks")
        )
        await callback.answer()
        return

    text = "⚡ <b>Активные задачи</b>\n\n"

    # Типы задач с эмодзи
    task_emojis = {
        'join_leave_groups': '🔄',
        'screenshot_spam': '📸',
        'mass_messaging': '💬',
        'voice_call': '📞',
        'set_reactions': '❤️',
        'subscribe_channel': '➕',
        'start_bot': '🤖',
        'cleanup_account': '🧹'
    }

    task_names = {
        'join_leave_groups': 'Вход/Выход из групп',
        'screenshot_spam': 'Скриншот-спам',
        'mass_messaging': 'Массовая рассылка',
        'voice_call': 'Голосовой чат',
        'set_reactions': 'Реакции',
        'subscribe_channel': 'Подписки',
        'start_bot': 'Запуск ботов',
        'cleanup_account': 'Очистка аккаунтов'
    }

    for task in tasks:
        emoji = task_emojis.get(task['task_type'], '⚙️')
        name = task_names.get(task['task_type'], task['task_type'])

        text += f"{emoji} <b>{name}</b>\n"
        text += f"   ID: {task['id']}\n"
        text += f"   Статус: {task['status']}\n"
        text += f"   Создана: {task['created_at'][:19]}\n"
        text += f"   /task_{task['id']}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_button("menu_tasks"),
        parse_mode="HTML"
    )
    await callback.answer()

# === ДЕТАЛИ ЗАДАЧИ ===

@router.callback_query(F.data.startswith("task_detail_"))
async def task_detail(callback: CallbackQuery):
    """Детали задачи"""
    task_id = int(callback.data.split("_")[-1])
    task = await db.get_task_by_id(task_id)

    if not task:
        await callback.answer("❌ Задача не найдена", show_alert=True)
        return

    task_names = {
        'join_leave_groups': 'Вход/Выход из групп',
        'screenshot_spam': 'Скриншот-спам',
        'mass_messaging': 'Массовая рассылка',
        'voice_call': 'Голосовой чат',
        'set_reactions': 'Реакции',
        'subscribe_channel': 'Подписки',
        'start_bot': 'Запуск ботов',
        'cleanup_account': 'Очистка аккаунтов'
    }

    name = task_names.get(task['task_type'], task['task_type'])

    text = f"""
📋 <b>Задача #{task['id']}</b>

<b>Тип:</b> {name}
<b>Статус:</b> {task['status']}
<b>Создана:</b> {task['created_at'][:19]}
"""

    if task['started_at']:
        text += f"<b>Запущена:</b> {task['started_at'][:19]}\n"

    if task['finished_at']:
        text += f"<b>Завершена:</b> {task['finished_at'][:19]}\n"

    # Конфиг
    try:
        config = json.loads(task['config'])
        text += f"\n<b>Конфигурация:</b>\n"
        for key, value in config.items():
            if isinstance(value, list) and len(value) > 3:
                text += f"  • {key}: {len(value)} элементов\n"
            else:
                text += f"  • {key}: {value}\n"
    except:
        pass

    # Результаты
    if task['results']:
        try:
            results = json.loads(task['results'])
            if isinstance(results, list):
                success = len([r for r in results if r.get('success')])
                text += f"\n<b>Результаты:</b>\n"
                text += f"  • Успешно: {success}/{len(results)}\n"
        except:
            pass

    await callback.message.edit_text(
        text,
        reply_markup=task_detail_kb(task_id),
        parse_mode="HTML"
    )
    await callback.answer()

# === ОСТАНОВКА ЗАДАЧ ===

@router.callback_query(F.data.startswith("task_stop_"))
async def task_stop(callback: CallbackQuery):
    """Остановить задачу"""
    task_id = int(callback.data.split("_")[-1])

    result = await task_manager.stop_task(task_id)

    if result:
        await callback.answer("✅ Задача остановлена", show_alert=True)
        # Обновляем детали
        await task_detail(callback)
    else:
        await callback.answer("❌ Не удалось остановить задачу", show_alert=True)

@router.callback_query(F.data == "tasks_stop_all")
async def tasks_stop_all(callback: CallbackQuery):
    """Остановить все задачи"""
    await callback.answer("⏳ Остановка всех задач...", show_alert=False)

    await task_manager.stop_all_tasks()

    await callback.message.edit_text(
        "✅ Все задачи остановлены!",
        reply_markup=back_button("menu_tasks")
    )

# === ИСТОРИЯ ===

@router.callback_query(F.data == "tasks_history")
async def tasks_history(callback: CallbackQuery):
    """История задач"""
    # Получаем все задачи из БД
    import aiosqlite

    async with aiosqlite.connect(db.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM tasks WHERE status IN ('completed', 'failed', 'stopped') ORDER BY id DESC LIMIT 10"
        )
        rows = await cursor.fetchall()
        tasks = [dict(row) for row in rows]

    if not tasks:
        await callback.message.edit_text(
            "📜 История пуста.",
            reply_markup=back_button("menu_tasks")
        )
        await callback.answer()
        return

    task_names = {
        'join_leave_groups': 'Вход/Выход',
        'screenshot_spam': 'Скриншот-спам',
        'mass_messaging': 'Рассылка',
        'voice_call': 'Голосовой чат',
        'set_reactions': 'Реакции',
        'subscribe_channel': 'Подписки',
        'start_bot': 'Запуск ботов',
        'cleanup_account': 'Очистка'
    }

    status_emoji = {
        'completed': '✅',
        'failed': '❌',
        'stopped': '⏹'
    }

    text = "📜 <b>История задач</b>\n\n"

    for task in tasks:
        emoji = status_emoji.get(task['status'], '❓')
        name = task_names.get(task['task_type'], task['task_type'])

        text += f"{emoji} {name} (ID: {task['id']})\n"
        text += f"   {task['finished_at'][:19] if task['finished_at'] else 'N/A'}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_button("menu_tasks"),
        parse_mode="HTML"
    )
    await callback.answer()
