from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
import json

from keyboards import (
    actions_menu_kb, select_accounts_kb, confirm_action_kb,
    back_button, cancel_button
)
from database import Database
from modules.account_manager import AccountManager
from modules.task_manager import TaskManager

router = Router()

# Глобальные переменные
db: Database = None
account_manager: AccountManager = None
task_manager: TaskManager = None

def setup(database: Database, acc_manager: AccountManager, tm: TaskManager):
    """Настройка зависимостей"""
    global db, account_manager, task_manager
    db = database
    account_manager = acc_manager
    task_manager = tm

# === STATES ===

class ActionStates(StatesGroup):
    select_accounts = State()
    configure = State()
    confirm = State()

# === МЕНЮ ДЕЙСТВИЙ ===

@router.callback_query(F.data == "menu_actions")
async def menu_actions(callback: CallbackQuery, state: FSMContext):
    """Меню действий"""
    await state.clear()

    text = """
🚀 <b>Запуск действий</b>

Выберите действие, которое хотите выполнить:
"""

    await callback.message.edit_text(
        text,
        reply_markup=actions_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

# === ВХОД/ВЫХОД ИЗ ГРУПП ===

@router.callback_query(F.data == "action_join_leave")
async def action_join_leave(callback: CallbackQuery, state: FSMContext):
    """Настройка входа/выхода из групп"""
    await state.update_data(action_type='join_leave_groups')

    accounts = await db.get_all_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    text = """
🔄 <b>Вход/Выход из групп</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_accounts_"))
async def select_accounts(callback: CallbackQuery, state: FSMContext):
    """Выбор количества аккаунтов"""
    selection = callback.data.split("_")[-1]

    accounts = await db.get_all_accounts(status='active')
    account_ids = [acc['id'] for acc in accounts]

    if selection == "all":
        selected_ids = account_ids
    elif selection == "custom":
        await callback.message.edit_text(
            "✏️ Введите количество аккаунтов (число):",
            reply_markup=cancel_button()
        )
        await state.set_state(ActionStates.select_accounts)
        await callback.answer()
        return
    else:
        count = int(selection)
        selected_ids = account_ids[:count]

    await state.update_data(account_ids=selected_ids)

    # Переход к настройке
    data = await state.get_data()
    action_type = data.get('action_type')

    if action_type == 'join_leave_groups':
        await configure_join_leave(callback, state)
    elif action_type == 'screenshot_spam':
        await configure_screenshot(callback, state)
    elif action_type == 'mass_messaging':
        await configure_mass_msg(callback, state)
    elif action_type == 'voice_call':
        await configure_voice(callback, state)
    elif action_type == 'reactions':
        await configure_reactions(callback, state)
    elif action_type == 'subscribe':
        await configure_subscribe(callback, state)
    elif action_type == 'start_bots':
        await configure_start_bots(callback, state)
    elif action_type == 'cleanup':
        await configure_cleanup(callback, state)

# === НАСТРОЙКА ДЕЙСТВИЙ ===

async def configure_join_leave(callback: CallbackQuery, state: FSMContext):
    """Настройка входа/выхода"""
    text = """
🔄 <b>Настройка входа/выхода</b>

Отправьте ссылку на группу и тип действия в формате:

<code>ссылка | действие | длительность(сек)</code>

<b>Действия:</b>
• join - войти в группу
• leave - выйти из группы
• cycle - циклично входить/выходить

<b>Примеры:</b>
<code>https://t.me/group | cycle | 3600</code>
<code>@group_username | join</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

@router.message(StateFilter(ActionStates.configure))
async def process_configure(message: Message, state: FSMContext):
    """Обработка настройки"""
    data = await state.get_data()
    action_type = data.get('action_type')

    try:
        await message.delete()
    except:
        pass

    if action_type == 'join_leave_groups':
        # Парсим: ссылка | действие | длительность
        parts = [p.strip() for p in message.text.split('|')]
        if len(parts) < 2:
            await message.answer("❌ Неверный формат. Попробуйте еще раз.")
            return

        config = {
            'group_link': parts[0],
            'action': parts[1] if len(parts) > 1 else 'cycle',
            'cycle_duration': int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 3600,
            'delay_min': 5,
            'delay_max': 15
        }

        await state.update_data(config=config)
        await show_confirmation(message, state)

# === ПОДТВЕРЖДЕНИЕ ===

async def show_confirmation(message: Message, state: FSMContext):
    """Показать подтверждение"""
    data = await state.get_data()
    account_ids = data.get('account_ids', [])
    config = data.get('config', {})
    action_type = data.get('action_type')

    action_names = {
        'join_leave_groups': '🔄 Вход/Выход из групп',
        'screenshot_spam': '📸 Скриншот-спам',
        'mass_messaging': '💬 Массовая рассылка',
        'voice_call': '📞 Голосовой чат',
        'reactions': '❤️ Реакции',
        'subscribe': '➕ Подписки',
        'start_bots': '🤖 Запуск ботов',
        'cleanup': '🧹 Очистка'
    }

    text = f"""
✅ <b>Подтверждение запуска</b>

<b>Действие:</b> {action_names.get(action_type, action_type)}
<b>Аккаунтов:</b> {len(account_ids)}

<b>Настройки:</b>
"""

    for key, value in config.items():
        if isinstance(value, list) and len(value) > 3:
            text += f"  • {key}: {len(value)} элементов\n"
        else:
            text += f"  • {key}: {value}\n"

    text += "\nЗапустить?"

    await message.answer(
        text,
        reply_markup=confirm_action_kb("start_task"),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.confirm)

@router.callback_query(F.data.startswith("confirm_"))
async def confirm_action(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и запуск"""
    data = await state.get_data()

    account_ids = data.get('account_ids', [])
    config = data.get('config', {})
    action_type = data.get('action_type')

    # Создаем задачу
    try:
        task_id = await task_manager.create_task(
            task_type=action_type,
            config=config,
            account_ids=account_ids
        )

        await state.clear()

        await callback.message.edit_text(
            f"✅ Задача #{task_id} запущена!\n\n"
            f"Отслеживайте прогресс в разделе 'Задачи'.",
            reply_markup=back_button("menu_main")
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка запуска: {str(e)}",
            reply_markup=back_button("menu_actions")
        )

    await callback.answer()

# === СКРИНШОТ-СПАМ ===

@router.callback_query(F.data == "action_screenshot")
async def action_screenshot(callback: CallbackQuery, state: FSMContext):
    """Скриншот-спам"""
    await state.update_data(action_type='screenshot_spam')

    accounts = await db.get_all_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    text = """
📸 <b>Скриншот-уведомления</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )
    await callback.answer()

async def configure_screenshot(callback: CallbackQuery, state: FSMContext):
    """Настройка скриншот-спама"""
    text = """
📸 <b>Настройка скриншот-спама</b>

Отправьте username пользователя и количество в формате:

<code>@username | количество</code>

<b>Пример:</b>
<code>@user123 | 100</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === МАССОВАЯ РАССЫЛКА ===

@router.callback_query(F.data == "action_mass_msg")
async def action_mass_msg(callback: CallbackQuery, state: FSMContext):
    """Массовая рассылка"""
    await state.update_data(action_type='mass_messaging')

    accounts = await db.get_all_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    text = """
💬 <b>Массовая рассылка</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )
    await callback.answer()

async def configure_mass_msg(callback: CallbackQuery, state: FSMContext):
    """Настройка массовой рассылки"""
    # Получаем шаблоны
    templates = await db.get_all_templates()

    if not templates:
        text = """
💬 <b>Настройка рассылки</b>

Отправьте данные в формате:

<code>ссылка_группы
сообщение1
сообщение2
сообщение3</code>

Каждое сообщение с новой строки.
"""
    else:
        template_list = "\n".join([f"• {t['name']}" for t in templates[:5]])
        text = f"""
💬 <b>Настройка рассылки</b>

<b>Доступные шаблоны:</b>
{template_list}

Отправьте данные в формате:

<code>ссылка_группы
сообщение1
сообщение2</code>

Или используйте шаблоны.
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === ГОЛОСОВЫЕ ВЫЗОВЫ ===

async def configure_voice(callback: CallbackQuery, state: FSMContext):
    """Настройка голосовых вызовов"""
    text = """
📞 <b>Настройка голосовых вызовов</b>

Отправьте ссылку на группу в формате:

<code>ссылка_группы</code>

<b>Пример:</b>
<code>https://t.me/group</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === РЕАКЦИИ ===

async def configure_reactions(callback: CallbackQuery, state: FSMContext):
    """Настройка реакций"""
    text = """
❤️ <b>Настройка реакций</b>

Отправьте ссылку на группу в формате:

<code>ссылка_группы</code>

<b>Пример:</b>
<code>https://t.me/group</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === ПОДПИСКИ ===

async def configure_subscribe(callback: CallbackQuery, state: FSMContext):
    """Настройка подписок"""
    text = """
➕ <b>Настройка подписок</b>

Отправьте список каналов/пользователей в формате:

<code>@channel1
@channel2
@user1</code>

Каждый с новой строки.
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === ЗАПУСК БОТОВ ===

async def configure_start_bots(callback: CallbackQuery, state: FSMContext):
    """Настройка запуска ботов"""
    text = """
🤖 <b>Настройка запуска ботов</b>

Отправьте список ботов в формате:

<code>@bot1
@bot2
@bot3</code>

Каждый бот с новой строки.
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === ОЧИСТКА ===

async def configure_cleanup(callback: CallbackQuery, state: FSMContext):
    """Настройка очистки"""
    text = """
🧹 <b>Настройка очистки</b>

Выберите что очистить:

<b>Опции:</b>
• all - всё (чаты, контакты, истории)
• chats - только чаты
• contacts - только контакты
• history - только историю

Отправьте опцию:
<code>all</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()

# === ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ (упрощенные заглушки) ===

@router.callback_query(F.data == "action_voice")
async def action_voice(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)

@router.callback_query(F.data == "action_reactions")
async def action_reactions(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)

@router.callback_query(F.data == "action_subscribe")
async def action_subscribe(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)

@router.callback_query(F.data == "action_start_bots")
async def action_start_bots(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)

@router.callback_query(F.data == "action_cleanup")
async def action_cleanup(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)
