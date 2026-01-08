from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
import json

from keyboards import (
    actions_menu_kb, select_accounts_kb, confirm_action_kb,
    back_button, cancel_button,
    get_playback_mode_keyboard, get_audio_files_keyboard,
    get_video_files_keyboard, get_enable_video_keyboard,
    get_duration_mode_keyboard
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
    # Голосовой чат состояния
    voice_group_link = State()
    voice_playback_mode = State()
    voice_select_audio = State()
    voice_enable_video = State()
    voice_select_video = State()
    voice_duration = State()

# === МЕНЮ ДЕЙСТВИЙ ===

@router.callback_query(F.data == "menu_actions")
async def menu_actions(callback: CallbackQuery, state: FSMContext):
    """Меню действий"""
    await callback.answer()
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

# === ВХОД/ВЫХОД ИЗ ГРУПП ===

@router.callback_query(F.data == "action_join_leave")
async def action_join_leave(callback: CallbackQuery, state: FSMContext):
    """Настройка входа/выхода из групп"""
    await state.update_data(action_type='join_leave_groups')

    accounts = await account_manager.get_valid_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    await callback.answer()

    text = """
🔄 <b>Вход/Выход из групп</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("select_accounts_"))
async def select_accounts(callback: CallbackQuery, state: FSMContext):
    """Выбор количества аккаунтов"""
    await callback.answer()

    selection = callback.data.split("_")[-1]

    accounts = await account_manager.get_valid_accounts(status='active')
    account_ids = [acc['id'] for acc in accounts]

    if selection == "all":
        selected_ids = account_ids
    elif selection == "custom":
        await callback.message.edit_text(
            "✏️ Введите количество аккаунтов (число):",
            reply_markup=cancel_button()
        )
        await state.set_state(ActionStates.select_accounts)
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
    elif action_type == 'set_reactions':
        await configure_reactions(callback, state)
    elif action_type == 'subscribe_channel':
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

    elif action_type == 'mass_messaging':
        # Проверяем, используются ли шаблоны
        use_templates = data.get('use_templates', False)

        if use_templates:
            # Если используются шаблоны, парсим: ссылка | количество
            parts = [p.strip() for p in message.text.split('|')]
            group_link = parts[0]
            message_count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100

            messages = data.get('messages', [])

            if not messages:
                await message.answer("❌ Ошибка: нет сохраненных сообщений из шаблонов.")
                return

            config = {
                'group_link': group_link,
                'messages': messages,
                'message_count': message_count,
                'delay_min': 5,
                'delay_max': 15
            }

            await state.update_data(config=config)
            await show_confirmation(message, state)
        else:
            # Если пользовательский текст, парсим ссылку, количество и сообщения
            lines = message.text.strip().split('\n')
            if len(lines) < 2:
                await message.answer("❌ Неверный формат. Нужна ссылка на группу и хотя бы одно сообщение.")
                return

            # Первая строка: ссылка | количество
            first_line_parts = [p.strip() for p in lines[0].split('|')]
            group_link = first_line_parts[0]
            message_count = int(first_line_parts[1]) if len(first_line_parts) > 1 and first_line_parts[1].isdigit() else 100

            # Остальные строки - сообщения
            messages = [line.strip() for line in lines[1:] if line.strip()]

            if not messages:
                await message.answer("❌ Нет сообщений для отправки.")
                return

            config = {
                'group_link': group_link,
                'messages': messages,
                'message_count': message_count,
                'delay_min': 5,
                'delay_max': 15
            }

            await state.update_data(config=config)
            await show_confirmation(message, state)

    elif action_type == 'screenshot_spam':
        # Парсим: @username | количество
        parts = [p.strip() for p in message.text.split('|')]
        if len(parts) < 2:
            await message.answer("❌ Неверный формат. Попробуйте еще раз.")
            return

        config = {
            'username': parts[0],
            'count': int(parts[1]) if parts[1].isdigit() else 100,
            'delay_min': 0,
            'delay_max': 0.5,
            'account_delay_min': 1,
            'account_delay_max': 3
        }

        await state.update_data(config=config)
        await show_confirmation(message, state)

    elif action_type == 'set_reactions':
        # Обрабатываем разные форматы
        lines = message.text.strip().split('\n')

        # Проверяем, указана ли ссылка-приглашение (для приватного канала)
        invite_link = None
        post_or_channel_link = None

        if len(lines) > 1:
            # Вариант с приватным каналом: первая строка - invite, вторая - пост
            invite_link = lines[0].strip()
            post_or_channel_link = lines[1].strip()
        else:
            # Обычный вариант
            post_or_channel_link = lines[0].strip()

        # Парсим основную строку: ссылка | параметры
        parts = [p.strip() for p in post_or_channel_link.split('|')]
        if len(parts) < 1:
            await message.answer("❌ Неверный формат. Попробуйте еще раз.")
            return

        link = parts[0]

        # Определяем, это ссылка на конкретный пост или на канал
        is_post_link = False
        if '/c/' in link or (link.count('/') >= 3 and link.split('/')[-1].isdigit()):
            is_post_link = True

        config = {
            'delay_min': 0,
            'delay_max': 1,
            'account_delay_min': 1,
            'account_delay_max': 3,
            'random_reactions': False
        }

        if is_post_link:
            # Это ссылка на конкретный пост
            config['post_link'] = link
            config['reaction'] = parts[1] if len(parts) > 1 else '👍'
        else:
            # Это ссылка на канал - ставим на последние посты
            config['group_link'] = link
            config['posts_count'] = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            config['reaction'] = parts[2] if len(parts) > 2 else '👍'

        # Добавляем invite_link, если указан
        if invite_link:
            config['invite_link'] = invite_link

        await state.update_data(config=config)
        await show_confirmation(message, state)

    elif action_type == 'subscribe_channel':
        # Парсим список каналов (каждый с новой строки)
        channels = [line.strip() for line in message.text.strip().split('\n') if line.strip()]

        if not channels:
            await message.answer("❌ Не указаны каналы для подписки.")
            return

        config = {
            'channels': channels,
            'delay_min': 0,
            'delay_max': 1,
            'account_delay_min': 2,
            'account_delay_max': 4
        }

        await state.update_data(config=config)
        await show_confirmation(message, state)

    elif action_type == 'start_bots':
        # Парсим: @bot_username | реферальный_код
        parts = [p.strip() for p in message.text.split('|')]
        if len(parts) < 1:
            await message.answer("❌ Неверный формат. Попробуйте еще раз.")
            return

        bot_username = parts[0]
        start_param = parts[1] if len(parts) > 1 else ''

        config = {
            'bot_username': bot_username,
            'start_param': start_param,
            'delay_min': 2,
            'delay_max': 5
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
        'set_reactions': '❤️ Реакции',
        'subscribe_channel': '➕ Подписки',
        'start_bots': '🤖 Запуск ботов',
        'cleanup': '🧹 Очистка'
    }

    text = f"""
✅ <b>Подтверждение запуска</b>

<b>Действие:</b> {action_names.get(action_type, action_type)}
<b>Аккаунтов:</b> {len(account_ids)}

<b>Настройки:</b>
"""

    # Специальное отображение для массовой рассылки
    if action_type == 'mass_messaging':
        text += f"  • Группа: {config.get('group_link', 'N/A')}\n"
        text += f"  • Уникальных сообщений: {len(config.get('messages', []))}\n"
        text += f"  • Сообщений на аккаунт: {config.get('message_count', 100)}\n"
        text += f"  • Задержка между сообщениями: {config.get('delay_min', 5)}-{config.get('delay_max', 15)} сек\n"
        text += f"\n💡 Сообщения будут повторяться циклично\n"
    else:
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
    await callback.answer()

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

# === СКРИНШОТ-СПАМ ===

@router.callback_query(F.data == "action_screenshot")
async def action_screenshot(callback: CallbackQuery, state: FSMContext):
    """Скриншот-спам"""
    await state.update_data(action_type='screenshot_spam')

    accounts = await account_manager.get_valid_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    await callback.answer()

    text = """
📸 <b>Скриншот-уведомления</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )

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

# === МАССОВАЯ РАССЫЛКА ===

@router.callback_query(F.data == "action_mass_msg")
async def action_mass_msg(callback: CallbackQuery, state: FSMContext):
    """Массовая рассылка"""
    await state.update_data(action_type='mass_messaging')

    accounts = await account_manager.get_valid_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    await callback.answer()

    text = """
💬 <b>Массовая рассылка</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )

async def configure_mass_msg(callback: CallbackQuery, state: FSMContext):
    """Настройка массовой рассылки"""
    from keyboards import message_source_kb

    # Получаем количество шаблонов
    templates = await db.get_all_templates()
    templates_count = len(templates)

    text = f"""
💬 <b>Настройка рассылки</b>

Выберите источник сообщений для рассылки:

📝 <b>Шаблоны</b> - использовать готовые сообщения из базы данных
   (Доступно шаблонов: {templates_count})

✏️ <b>Свой текст</b> - написать собственные сообщения для рассылки
"""

    await callback.message.edit_text(
        text,
        reply_markup=message_source_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "msg_source_templates")
async def msg_source_templates(callback: CallbackQuery, state: FSMContext):
    """Использование шаблонов для рассылки"""
    await callback.answer()

    # Получаем все шаблоны из базы данных
    templates = await db.get_all_templates()

    if not templates:
        await callback.answer("❌ Нет доступных шаблонов", show_alert=True)
        return

    # Извлекаем содержимое всех шаблонов
    messages = [template['content'] for template in templates]

    # Сохраняем в состоянии, что используются шаблоны
    await state.update_data(use_templates=True, messages=messages)

    text = f"""
💬 <b>Настройка рассылки с шаблонами</b>

✅ Загружено {len(messages)} сообщений из шаблонов.

Теперь отправьте данные в формате:

<code>ссылка_группы | количество_сообщений</code>

<b>Примеры:</b>
<code>https://t.me/group_name | 100</code>
<code>@group_username | 500</code>

Если не указать количество, каждый аккаунт отправит по 100 сообщений.
Сообщения будут выбираться случайно из шаблонов и повторяться циклично.
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)

@router.callback_query(F.data == "msg_source_custom")
async def msg_source_custom(callback: CallbackQuery, state: FSMContext):
    """Пользовательский текст для рассылки"""
    await callback.answer()

    # Сохраняем в состоянии, что используется пользовательский текст
    await state.update_data(use_templates=False)

    text = """
💬 <b>Настройка рассылки с пользовательским текстом</b>

Отправьте данные в формате:

<code>ссылка_группы | количество_сообщений
сообщение1
сообщение2
сообщение3</code>

<b>Примеры:</b>
<code>https://t.me/group_name | 100
Привет!
Как дела?
Отличный день!</code>

Первая строка: ссылка на группу и количество сообщений (через |).
Остальные строки: ваши сообщения.
Сообщения будут повторяться циклично до достижения указанного количества.
Если не указать количество, по умолчанию будет 100 сообщений.
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)

# === ГОЛОСОВЫЕ ВЫЗОВЫ ===

async def configure_voice(callback: CallbackQuery, state: FSMContext):
    """Настройка голосовых вызовов - Шаг 1: Ссылка на группу"""
    text = """
📞 <b>Настройка голосовых вызовов</b>

Отправьте ссылку на группу, в которой нужно запустить голосовой чат:

<b>Пример:</b>
<code>https://t.me/your_group</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.voice_group_link)

@router.message(StateFilter(ActionStates.voice_group_link))
async def voice_group_link_received(message: Message, state: FSMContext):
    """Получена ссылка на группу - Шаг 2: Выбор режима воспроизведения"""
    group_link = message.text.strip()

    # Сохраняем ссылку
    await state.update_data(group_link=group_link)

    text = """
🎵 <b>Выберите режим воспроизведения:</b>

<b>Синхронно</b> - все аккаунты одновременно воспроизводят один файл
<b>По очереди</b> - аккаунты играют файл последовательно (relay)
<b>Случайные</b> - каждый аккаунт играет случайный файл из папки
"""

    await message.answer(
        text,
        reply_markup=get_playback_mode_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.voice_playback_mode)

@router.callback_query(F.data.startswith("playback_mode_"))
async def playback_mode_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран режим воспроизведения - Шаг 3: Выбор аудиофайла"""
    await callback.answer()

    playback_mode = callback.data.replace("playback_mode_", "")
    await state.update_data(playback_mode=playback_mode)

    # Получаем список аудиофайлов
    from modules.voice_calls import get_available_audio_files
    audio_files = get_available_audio_files()

    if not audio_files and playback_mode != 'random':
        await callback.message.edit_text(
            "❌ <b>Ошибка:</b> Нет аудиофайлов в папке audio/\n\n"
            "Добавьте аудиофайлы (MP3, WAV, OGG, M4A, FLAC) в папку audio/ и попробуйте снова.",
            reply_markup=back_button("menu_actions"),
            parse_mode="HTML"
        )
        return

    mode_names = {
        'sync': 'Синхронно',
        'relay': 'По очереди',
        'random': 'Случайные файлы'
    }

    if playback_mode == 'random':
        # Для random режима сразу переходим к вопросу о видео
        text = f"""
✅ <b>Режим:</b> {mode_names.get(playback_mode, playback_mode)}

📹 <b>Включить видео?</b>

Если включите видео, аккаунты зайдут в видеочат и будут транслировать видеофайл со звуком.
"""
        await callback.message.edit_text(
            text,
            reply_markup=get_enable_video_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(ActionStates.voice_enable_video)
    else:
        # Показываем список аудиофайлов
        text = f"""
✅ <b>Режим:</b> {mode_names.get(playback_mode, playback_mode)}

🎵 <b>Выберите аудиофайл:</b>
"""
        await callback.message.edit_text(
            text,
            reply_markup=get_audio_files_keyboard(audio_files),
            parse_mode="HTML"
        )
        await state.set_state(ActionStates.voice_select_audio)

@router.callback_query(F.data.startswith("audio_file_"))
async def audio_file_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран аудиофайл - Шаг 4: Включить видео?"""
    await callback.answer()

    audio_file = callback.data.replace("audio_file_", "")
    await state.update_data(audio_file=audio_file)

    text = f"""
✅ <b>Аудиофайл:</b> {audio_file}

📹 <b>Включить видео?</b>

Если включите видео, аккаунты зайдут в видеочат и будут транслировать видеофайл вместе с аудио.
"""

    await callback.message.edit_text(
        text,
        reply_markup=get_enable_video_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.voice_enable_video)

@router.callback_query(F.data.startswith("enable_video_"))
async def enable_video_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрано включение видео - Шаг 5: Выбор видеофайла (если нужно) или длительность"""
    await callback.answer()

    enable_video = callback.data == "enable_video_yes"
    await state.update_data(enable_video=enable_video)

    if enable_video:
        # Получаем список видеофайлов
        from modules.voice_calls import get_available_video_files
        video_files = get_available_video_files()

        if not video_files:
            await callback.message.edit_text(
                "❌ <b>Ошибка:</b> Нет видеофайлов в папке video/\n\n"
                "Добавьте видеофайлы (MP4, AVI, MKV, MOV, WebM) в папку video/ и попробуйте снова.",
                reply_markup=back_button("menu_actions"),
                parse_mode="HTML"
            )
            return

        text = """
🎬 <b>Выберите видеофайл:</b>
"""
        await callback.message.edit_text(
            text,
            reply_markup=get_video_files_keyboard(video_files),
            parse_mode="HTML"
        )
        await state.set_state(ActionStates.voice_select_video)
    else:
        # Переходим к выбору длительности
        await ask_duration(callback.message, state)

@router.callback_query(F.data.startswith("video_file_"))
async def video_file_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран видеофайл - Шаг 6: Длительность"""
    await callback.answer()

    video_file = callback.data.replace("video_file_", "")
    await state.update_data(video_file=video_file)

    await ask_duration(callback.message, state)

async def ask_duration(message: Message, state: FSMContext):
    """Спрашиваем о длительности"""
    text = """
⏱️ <b>Длительность пребывания в чате:</b>

Как долго аккаунты должны оставаться в голосовом чате?
"""

    await message.edit_text(
        text,
        reply_markup=get_duration_mode_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.voice_duration)

@router.callback_query(F.data.startswith("duration_mode_"))
async def duration_mode_selected(callback: CallbackQuery, state: FSMContext):
    """Выбран режим длительности"""
    await callback.answer()

    duration_mode = callback.data.replace("duration_mode_", "")

    if duration_mode == "infinite":
        # Бесконечный режим
        await state.update_data(duration=0)
        await show_voice_summary(callback, state)
    else:
        # Запрашиваем пользовательское время
        text = """
⏱️ <b>Укажите время в секундах:</b>

Например: <code>60</code> (1 минута), <code>300</code> (5 минут)
"""
        await callback.message.edit_text(
            text,
            reply_markup=cancel_button(),
            parse_mode="HTML"
        )
        # Остаемся в том же состоянии, но ждем текстовое сообщение

@router.message(StateFilter(ActionStates.voice_duration))
async def duration_value_received(message: Message, state: FSMContext):
    """Получено значение длительности"""
    try:
        duration = int(message.text.strip())
        if duration < 0:
            raise ValueError

        await state.update_data(duration=duration)
        await show_voice_summary(message, state)

    except ValueError:
        await message.answer(
            "❌ Неверный формат. Укажите положительное число секунд.",
            reply_markup=cancel_button()
        )

async def show_voice_summary(message_or_callback, state: FSMContext):
    """Показываем итоговую сводку и подтверждение"""
    data = await state.get_data()

    playback_mode = data.get('playback_mode', 'sync')
    audio_file = data.get('audio_file', 'Случайный')
    enable_video = data.get('enable_video', False)
    video_file = data.get('video_file', '-')
    duration = data.get('duration', 0)
    group_link = data.get('group_link', '')

    mode_names = {
        'sync': '🎵 Синхронно (все вместе)',
        'relay': '🔁 По очереди (relay)',
        'random': '🎲 Случайные файлы'
    }

    duration_text = "♾️ До ручной остановки" if duration == 0 else f"⏱️ {duration} секунд"

    text = f"""
📞 <b>Сводка настроек голосового чата</b>

<b>Группа:</b> {group_link}
<b>Режим:</b> {mode_names.get(playback_mode, playback_mode)}
<b>Аудио:</b> {audio_file}
<b>Видео:</b> {'📹 Да (' + video_file + ')' if enable_video else '🎵 Нет'}
<b>Длительность:</b> {duration_text}

Готовы запустить?
"""

    # Сохраняем конфигурацию для запуска задачи
    config = {
        'group_link': group_link,
        'audio_file': audio_file if audio_file != 'Случайный' else None,
        'playback_mode': playback_mode,
        'enable_video': enable_video,
        'video_file': video_file if enable_video else None,
        'duration': duration
    }

    await state.update_data(action_type='voice_call', config=config)

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(
            text,
            reply_markup=confirm_action_kb('voice_call'),
            parse_mode="HTML"
        )
    else:
        await message_or_callback.message.edit_text(
            text,
            reply_markup=confirm_action_kb('voice_call'),
            parse_mode="HTML"
        )

    await state.set_state(ActionStates.confirm)

# === РЕАКЦИИ ===

async def configure_reactions(callback: CallbackQuery, state: FSMContext):
    """Настройка реакций"""
    text = """
❤️ <b>Настройка реакций</b>

<b>Вариант 1 - Ссылка на пост:</b>
<code>https://t.me/channel/123 | эмодзи</code>

<b>Вариант 2 - Последние посты канала:</b>
<code>https://t.me/channel | количество_постов | эмодзи</code>

<b>Вариант 3 - Приватный канал:</b>
<code>https://t.me/+invite_hash
https://t.me/c/channel_id/message_id | эмодзи</code>

<b>Примеры:</b>
<code>https://t.me/channel/5432 | 🔥</code>
<code>https://t.me/channel | 10 | ❤️</code>
<code>https://t.me/+ABC123xyz
https://t.me/c/1234567890/100 | 👍</code>

<b>Доступные реакции:</b>
👍 👎 ❤️ 🔥 🥰 👏 😁 🤔 🤯 😱 🤬 😢 🎉 🤩 🤮 💩 🙏 👌 🕊 🤡
🥱 🥴 😍 🐳 ❤️‍🔥 🌚 🌭 💯 🤣 ⚡ 🍌 🏆 💔 🤨 😐 🍓 🍾 💋 😈
😴 😭 🤓 👻 👨‍💻 👀 🎃 🙈 😇 😨 🤝 ✍️ 🤗 🫡 и другие

Если не указать эмодзи, будет использован 👍
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)

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

# === ЗАПУСК БОТОВ ===

async def configure_start_bots(callback: CallbackQuery, state: FSMContext):
    """Настройка запуска ботов"""
    text = """
🤖 <b>Настройка запуска ботов</b>

Отправьте данные в формате:

<code>@bot_username | реферальный_код</code>

<b>Примеры:</b>
<code>@example_bot | ref_12345</code>
<code>@game_bot | start=abc123</code>
<code>@simple_bot</code> (без реферального кода)

<b>Как работает:</b>
• Все выбранные аккаунты запустят указанного бота
• Если указан реферальный код, он будет добавлен к команде /start
• Например: /start ref_12345

<b>Важно:</b>
• Используйте @ перед именем бота
• Реферальный код опционален
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)

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

# === ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ (упрощенные заглушки) ===

@router.callback_query(F.data == "action_voice")
async def action_voice(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)

@router.callback_query(F.data == "action_reactions")
async def action_reactions(callback: CallbackQuery, state: FSMContext):
    """Реакции"""
    await state.update_data(action_type='set_reactions')

    accounts = await account_manager.get_valid_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    await callback.answer()

    text = """
❤️ <b>Постановка реакций</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "action_subscribe")
async def action_subscribe(callback: CallbackQuery, state: FSMContext):
    """Подписки"""
    await state.update_data(action_type='subscribe_channel')

    accounts = await account_manager.get_valid_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    await callback.answer()

    text = """
➕ <b>Подписка на каналы</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "action_start_bots")
async def action_start_bots(callback: CallbackQuery, state: FSMContext):
    """Запуск ботов"""
    await state.update_data(action_type='start_bots')

    accounts = await account_manager.get_valid_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    await callback.answer()

    text = """
🤖 <b>Запуск ботов</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "action_cleanup")
async def action_cleanup(callback: CallbackQuery):
    await callback.answer("⚠️ Функция в разработке", show_alert=True)
