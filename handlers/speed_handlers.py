from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from keyboards import back_button, cancel_button
from database import Database

router = Router()

# Глобальные переменные
db: Database = None

def setup(database: Database):
    """Настройка зависимостей"""
    global db
    db = database

# === STATES ===

class SpeedStates(StatesGroup):
    select_action = State()
    configure_speed = State()

# === МЕНЮ НАСТРОЕК СКОРОСТИ ===

@router.callback_query(F.data == "settings_speed")
async def settings_speed(callback: CallbackQuery, state: FSMContext):
    """Меню настроек скорости"""
    await callback.answer()
    await state.clear()

    from keyboards import speed_settings_menu_kb

    text = """
⚡ <b>Настройки скорости действий</b>

Здесь вы можете настроить задержки для каждого типа действий.
Это позволяет контролировать скорость выполнения операций:

• <b>Задержка между действиями</b> - пауза между отправкой сообщений/реакций
• <b>Задержка между аккаунтами</b> - пауза перед переключением на следующий аккаунт

⚠️ <b>Внимание:</b> Слишком маленькие задержки могут привести к блокировке аккаунтов!

Выберите действие для настройки:
"""

    await callback.message.edit_text(
        text,
        reply_markup=speed_settings_menu_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("speed_config_"))
async def speed_config_action(callback: CallbackQuery, state: FSMContext):
    """Настройка скорости для конкретного действия"""
    await callback.answer()

    action_type = callback.data.replace("speed_config_", "")

    # Получаем текущие настройки
    current_settings = await db.get_speed_settings(action_type)

    action_names = {
        'mass_messaging': '💬 Массовая рассылка',
        'screenshot_spam': '📸 Скриншот-спам',
        'set_reactions': '❤️ Реакции',
        'subscribe_channel': '➕ Подписки',
        'start_bots': '🤖 Запуск ботов'
    }

    action_name = action_names.get(action_type, action_type)

    if current_settings:
        delay_min = current_settings.get('delay_min', 1.0)
        delay_max = current_settings.get('delay_max', 3.0)
        account_delay_min = current_settings.get('account_delay_min', 2.0)
        account_delay_max = current_settings.get('account_delay_max', 5.0)

        current_text = f"""
<b>Текущие настройки:</b>
• Задержка между действиями: {delay_min}-{delay_max} сек
• Задержка между аккаунтами: {account_delay_min}-{account_delay_max} сек
"""
    else:
        current_text = "\n<i>Настройки по умолчанию</i>\n"

    text = f"""
⚡ <b>Настройка скорости: {action_name}</b>

{current_text}

Отправьте новые настройки в формате:
<code>задержка_мин | задержка_макс | аккаунт_мин | аккаунт_макс</code>

<b>Примеры:</b>
<code>0 | 1 | 1 | 3</code> - очень быстро
<code>1 | 3 | 2 | 5</code> - умеренно
<code>5 | 10 | 10 | 15</code> - медленно (безопасно)

<b>Значения в секундах.</b>
Укажите 0 для минимальной задержки (без паузы).
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )

    await state.update_data(action_type=action_type)
    await state.set_state(SpeedStates.configure_speed)

@router.message(StateFilter(SpeedStates.configure_speed))
async def process_speed_config(message: Message, state: FSMContext):
    """Обработка настройки скорости"""
    data = await state.get_data()
    action_type = data.get('action_type')

    try:
        await message.delete()
    except:
        pass

    # Парсим настройки
    parts = [p.strip() for p in message.text.split('|')]
    if len(parts) < 4:
        await message.answer("❌ Неверный формат. Нужно указать 4 значения через |")
        return

    try:
        delay_min = float(parts[0])
        delay_max = float(parts[1])
        account_delay_min = float(parts[2])
        account_delay_max = float(parts[3])

        # Проверка валидности
        if delay_min < 0 or delay_max < 0 or account_delay_min < 0 or account_delay_max < 0:
            await message.answer("❌ Значения не могут быть отрицательными")
            return

        if delay_min > delay_max or account_delay_min > account_delay_max:
            await message.answer("❌ Минимальное значение не может быть больше максимального")
            return

        # Сохраняем настройки
        await db.set_speed_settings(
            action_type=action_type,
            delay_min=delay_min,
            delay_max=delay_max,
            message_delay_min=delay_min,  # Для совместимости
            message_delay_max=delay_max,
            account_delay_min=account_delay_min,
            account_delay_max=account_delay_max
        )

        await state.clear()

        action_names = {
            'mass_messaging': '💬 Массовая рассылка',
            'screenshot_spam': '📸 Скриншот-спам',
            'set_reactions': '❤️ Реакции',
            'subscribe_channel': '➕ Подписки',
            'start_bots': '🤖 Запуск ботов'
        }

        await message.answer(
            f"✅ Настройки скорости для '{action_names.get(action_type, action_type)}' сохранены!\n\n"
            f"• Задержка между действиями: {delay_min}-{delay_max} сек\n"
            f"• Задержка между аккаунтами: {account_delay_min}-{account_delay_max} сек",
            reply_markup=back_button("settings_speed")
        )

    except ValueError:
        await message.answer("❌ Ошибка: значения должны быть числами")
