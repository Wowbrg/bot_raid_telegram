from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# === ГЛАВНОЕ МЕНЮ ===

def main_menu_kb(is_super_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню бота"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Аккаунты", callback_data="menu_accounts"),
        InlineKeyboardButton(text="⚡ Задачи", callback_data="menu_tasks")
    )
    builder.row(
        InlineKeyboardButton(text="🚀 Запустить действие", callback_data="menu_actions"),
        InlineKeyboardButton(text="📝 Шаблоны", callback_data="menu_templates")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu_settings"),
        InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")
    )
    # Кнопка управления админами только для супер-админа
    if is_super_admin:
        builder.row(
            InlineKeyboardButton(text="👥 Админы", callback_data="menu_admins")
        )
    return builder.as_markup()

# === МЕНЮ АККАУНТОВ ===

def accounts_menu_kb() -> InlineKeyboardMarkup:
    """Меню управления аккаунтами"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Список аккаунтов", callback_data="accounts_list"),
        InlineKeyboardButton(text="➕ Добавить", callback_data="accounts_add")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Проверить здоровье", callback_data="accounts_health"),
        InlineKeyboardButton(text="🔄 Синхронизация", callback_data="accounts_sync")
    )
    builder.row(
        InlineKeyboardButton(text="🧹 Управление сессиями", callback_data="accounts_sessions")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")
    )
    return builder.as_markup()

def accounts_list_kb(page: int, total_pages: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    """Клавиатура для списка аккаунтов с пагинацией"""
    builder = InlineKeyboardBuilder()

    # Навигация
    nav_buttons = []
    if has_prev:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"accounts_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="▶️ Вперед", callback_data=f"accounts_page_{page+1}"))

    builder.row(*nav_buttons)
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"accounts_page_{page}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_accounts")
    )
    return builder.as_markup()

def account_detail_kb(account_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для конкретного аккаунта"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Проверить", callback_data=f"account_check_{account_id}"),
        InlineKeyboardButton(text="📊 Сессии", callback_data=f"account_sessions_{account_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"account_delete_{account_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="accounts_list")
    )
    return builder.as_markup()

# === МЕНЮ ДЕЙСТВИЙ ===

def actions_menu_kb() -> InlineKeyboardMarkup:
    """Меню выбора действий"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔄 Вход/Выход из групп", callback_data="action_join_leave"),
    )
    builder.row(
        InlineKeyboardButton(text="📸 Скриншот-спам", callback_data="action_screenshot"),
    )
    builder.row(
        InlineKeyboardButton(text="💬 Массовая рассылка", callback_data="action_mass_msg"),
    )
    builder.row(
        InlineKeyboardButton(text="📞 Голосовой чат", callback_data="action_voice"),
    )
    builder.row(
        InlineKeyboardButton(text="❤️ Реакции", callback_data="action_reactions"),
        InlineKeyboardButton(text="➕ Подписки", callback_data="action_subscribe")
    )
    builder.row(
        InlineKeyboardButton(text="🤖 Запуск ботов", callback_data="action_start_bots"),
        InlineKeyboardButton(text="🧹 Очистка аккаунтов", callback_data="action_cleanup")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")
    )
    return builder.as_markup()

def select_accounts_kb(total_accounts: int) -> InlineKeyboardMarkup:
    """Выбор количества аккаунтов для использования"""
    builder = InlineKeyboardBuilder()

    # Кнопки для быстрого выбора
    if total_accounts >= 1:
        builder.row(InlineKeyboardButton(text="1 аккаунт", callback_data="select_accounts_1"))
    if total_accounts >= 3:
        builder.row(InlineKeyboardButton(text="3 аккаунта", callback_data="select_accounts_3"))
    if total_accounts >= 5:
        builder.row(InlineKeyboardButton(text="5 аккаунтов", callback_data="select_accounts_5"))
    if total_accounts >= 10:
        builder.row(InlineKeyboardButton(text="10 аккаунтов", callback_data="select_accounts_10"))

    builder.row(InlineKeyboardButton(text="✅ Все аккаунты", callback_data="select_accounts_all"))
    builder.row(InlineKeyboardButton(text="✏️ Указать свое число", callback_data="select_accounts_custom"))
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="menu_actions"))

    return builder.as_markup()

def confirm_action_kb(action_data: str) -> InlineKeyboardMarkup:
    """Подтверждение запуска действия"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Запустить", callback_data=f"confirm_{action_data}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="menu_actions")
    )
    return builder.as_markup()

# === МЕНЮ ЗАДАЧ ===

def tasks_menu_kb() -> InlineKeyboardMarkup:
    """Меню управления задачами"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Активные задачи", callback_data="tasks_active"),
        InlineKeyboardButton(text="📜 История", callback_data="tasks_history")
    )
    builder.row(
        InlineKeyboardButton(text="⛔ Остановить все", callback_data="tasks_stop_all"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")
    )
    return builder.as_markup()

def task_detail_kb(task_id: int) -> InlineKeyboardMarkup:
    """Детали задачи"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⛔ Остановить", callback_data=f"task_stop_{task_id}"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"task_detail_{task_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="tasks_active")
    )
    return builder.as_markup()

# === МЕНЮ ШАБЛОНОВ ===

def templates_menu_kb() -> InlineKeyboardMarkup:
    """Меню шаблонов сообщений"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Список шаблонов", callback_data="templates_list"),
        InlineKeyboardButton(text="➕ Добавить", callback_data="templates_add")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")
    )
    return builder.as_markup()

def templates_list_kb(page: int, total_pages: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    """Клавиатура для списка шаблонов с пагинацией"""
    builder = InlineKeyboardBuilder()

    # Навигация
    nav_buttons = []
    if has_prev:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"templates_page_{page-1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="▶️ Вперед", callback_data=f"templates_page_{page+1}"))

    builder.row(*nav_buttons)
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"templates_page_{page}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_templates")
    )
    return builder.as_markup()

def template_detail_kb(template_id: int) -> InlineKeyboardMarkup:
    """Детали шаблона"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"template_delete_{template_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="templates_list")
    )
    return builder.as_markup()

# === МЕНЮ НАСТРОЕК ===

def settings_menu_kb() -> InlineKeyboardMarkup:
    """Меню настроек"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔧 Общие настройки", callback_data="settings_general"),
    )
    builder.row(
        InlineKeyboardButton(text="⚡ Настройки скорости", callback_data="settings_speed"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")
    )
    return builder.as_markup()

def speed_settings_menu_kb() -> InlineKeyboardMarkup:
    """Меню настроек скорости"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 Массовая рассылка", callback_data="speed_config_mass_messaging")
    )
    builder.row(
        InlineKeyboardButton(text="📸 Скриншот-спам", callback_data="speed_config_screenshot_spam")
    )
    builder.row(
        InlineKeyboardButton(text="❤️ Реакции", callback_data="speed_config_set_reactions")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Подписки", callback_data="speed_config_subscribe_channel")
    )
    builder.row(
        InlineKeyboardButton(text="🤖 Запуск ботов", callback_data="speed_config_start_bots")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_settings")
    )
    return builder.as_markup()

# === УНИВЕРСАЛЬНЫЕ КНОПКИ ===

def back_button(callback_data: str = "menu_main") -> InlineKeyboardMarkup:
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data))
    return builder.as_markup()

def cancel_button() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main"))
    return builder.as_markup()

def message_source_kb() -> InlineKeyboardMarkup:
    """Выбор источника сообщений для рассылки"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 Использовать шаблоны", callback_data="msg_source_templates")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Написать свой текст", callback_data="msg_source_custom")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Отмена", callback_data="menu_actions")
    )
    return builder.as_markup()
