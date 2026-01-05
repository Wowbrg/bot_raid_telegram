from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
import math

from keyboards import (
    accounts_menu_kb, accounts_list_kb, account_detail_kb,
    back_button, cancel_button
)
from database import Database
from modules.account_manager import AccountManager
import config

router = Router()

# Глобальные переменные для зависимостей
db: Database = None
account_manager: AccountManager = None

def setup(database: Database, acc_manager: AccountManager):
    """Настройка зависимостей"""
    global db, account_manager
    db = database
    account_manager = acc_manager

# === STATES ===

class AddAccountStates(StatesGroup):
    phone = State()
    code = State()
    password = State()

# === МЕНЮ АККАУНТОВ ===

@router.callback_query(F.data == "menu_accounts")
async def menu_accounts(callback: CallbackQuery):
    """Меню аккаунтов"""
    accounts = await db.get_all_accounts()
    total = len(accounts)
    active = len([a for a in accounts if a['status'] == 'active'])

    text = f"""
📱 <b>Управление аккаунтами</b>

📊 Статистика:
• Всего аккаунтов: {total}
• Активных: {active}
• Неактивных: {total - active}

Выберите действие:
"""

    await callback.message.edit_text(
        text,
        reply_markup=accounts_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

# === СПИСОК АККАУНТОВ ===

@router.callback_query(F.data == "accounts_list")
async def accounts_list(callback: CallbackQuery):
    """Первая страница списка аккаунтов"""
    await show_accounts_page(callback, 1)

@router.callback_query(F.data.startswith("accounts_page_"))
async def accounts_page(callback: CallbackQuery):
    """Переход на страницу списка"""
    page = int(callback.data.split("_")[-1])
    await show_accounts_page(callback, page)

async def show_accounts_page(callback: CallbackQuery, page: int):
    """Показать страницу со списком аккаунтов"""
    accounts = await db.get_all_accounts()

    if not accounts:
        await callback.message.edit_text(
            "📱 У вас пока нет аккаунтов.\n\nДобавьте первый аккаунт!",
            reply_markup=back_button("menu_accounts")
        )
        await callback.answer()
        return

    # Пагинация
    per_page = config.MAX_ACCOUNTS_PER_PAGE
    total_pages = math.ceil(len(accounts) / per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_accounts = accounts[start_idx:end_idx]

    # Формируем текст
    text = f"📱 <b>Список аккаунтов</b> (страница {page}/{total_pages})\n\n"

    for acc in page_accounts:
        status_emoji = {
            'active': '✅',
            'inactive': '⚠️',
            'banned': '🚫',
            'error': '❌',
            'unauthorized': '🔐'
        }.get(acc['status'], '❓')

        text += f"{status_emoji} <b>ID {acc['id']}</b> • {acc['phone']}\n"
        text += f"   Статус: {acc['status']}"

        if acc['last_error']:
            text += f"\n   Ошибка: {acc['last_error'][:50]}..."

        text += f"\n   /account_{acc['id']}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=accounts_list_kb(
            page,
            total_pages,
            page > 1,
            page < total_pages
        ),
        parse_mode="HTML"
    )
    await callback.answer()

# === ДОБАВЛЕНИЕ АККАУНТА ===

@router.callback_query(F.data == "accounts_add")
async def accounts_add(callback: CallbackQuery, state: FSMContext):
    """Начать добавление аккаунта"""
    await callback.message.edit_text(
        "📱 <b>Добавление нового аккаунта</b>\n\n"
        "Отправьте номер телефона в международном формате.\n"
        "Например: <code>+1234567890</code>",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(AddAccountStates.phone)
    await callback.answer()

@router.message(StateFilter(AddAccountStates.phone))
async def process_phone(message: Message, state: FSMContext):
    """Обработка номера телефона"""
    phone = message.text.strip()

    # Валидация
    if not phone.startswith('+') or not phone[1:].isdigit():
        await message.answer(
            "❌ Неверный формат номера.\n\n"
            "Используйте международный формат, например: +1234567890"
        )
        return

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass

    # Пытаемся добавить аккаунт
    msg = await message.answer("⏳ Отправка кода...")

    result = await account_manager.add_new_account(phone)

    if result['status'] == 'code_sent':
        await state.update_data(phone=phone, session_name=result['session_name'])
        await state.set_state(AddAccountStates.code)
        await msg.edit_text(
            "📱 <b>Код отправлен!</b>\n\n"
            "Введите код подтверждения из Telegram:",
            parse_mode="HTML"
        )

    elif result['status'] == 'success':
        await state.clear()
        await msg.edit_text(
            f"✅ Аккаунт успешно добавлен!\n\n"
            f"ID: {result['account_id']}",
            reply_markup=back_button("menu_accounts")
        )

    else:
        await state.clear()
        await msg.edit_text(
            f"❌ Ошибка: {result['message']}",
            reply_markup=back_button("menu_accounts")
        )

@router.message(StateFilter(AddAccountStates.code))
async def process_code(message: Message, state: FSMContext):
    """Обработка кода подтверждения"""
    code = message.text.strip()
    data = await state.get_data()

    # Удаляем сообщение
    try:
        await message.delete()
    except:
        pass

    msg = await message.answer("⏳ Проверка кода...")

    result = await account_manager.verify_code(data['phone'], code)

    if result['status'] == 'password_required':
        await state.set_state(AddAccountStates.password)
        await msg.edit_text(
            "🔐 <b>Требуется пароль 2FA</b>\n\n"
            "Введите пароль двухфакторной аутентификации:",
            parse_mode="HTML"
        )

    elif result['status'] == 'success':
        await state.clear()
        await msg.edit_text(
            f"✅ Аккаунт успешно добавлен!\n\n"
            f"ID: {result['account_id']}",
            reply_markup=back_button("menu_accounts")
        )

    else:
        await msg.edit_text(
            f"❌ Ошибка: {result['message']}\n\n"
            "Попробуйте еще раз или отмените операцию.",
            reply_markup=cancel_button()
        )

@router.message(StateFilter(AddAccountStates.password))
async def process_password(message: Message, state: FSMContext):
    """Обработка пароля 2FA"""
    password = message.text.strip()
    data = await state.get_data()

    # Удаляем сообщение
    try:
        await message.delete()
    except:
        pass

    msg = await message.answer("⏳ Проверка пароля...")

    # Получаем последний код из данных состояния
    code = data.get('last_code', '')

    result = await account_manager.verify_code(data['phone'], code, password)

    if result['status'] == 'success':
        await state.clear()
        await msg.edit_text(
            f"✅ Аккаунт успешно добавлен!\n\n"
            f"ID: {result['account_id']}",
            reply_markup=back_button("menu_accounts")
        )
    else:
        await state.clear()
        await msg.edit_text(
            f"❌ Ошибка: {result['message']}",
            reply_markup=back_button("menu_accounts")
        )

# === ПРОВЕРКА ЗДОРОВЬЯ ===

@router.callback_query(F.data == "accounts_health")
async def accounts_health(callback: CallbackQuery):
    """Проверка состояния всех аккаунтов"""
    await callback.answer("⏳ Проверка аккаунтов...", show_alert=False)

    accounts = await db.get_all_accounts(status='active')

    if not accounts:
        await callback.message.edit_text(
            "❌ Нет активных аккаунтов для проверки.",
            reply_markup=back_button("menu_accounts")
        )
        return

    msg = await callback.message.edit_text(
        f"🔍 Проверка {len(accounts)} аккаунтов...\n\nЭто может занять некоторое время."
    )

    results = []
    for acc in accounts[:10]:  # Ограничиваем 10 аккаунтами за раз
        health = await account_manager.check_account_health(acc['id'])
        results.append({
            'id': acc['id'],
            'phone': acc['phone'],
            'health': health
        })

    # Формируем отчет
    text = "📊 <b>Результаты проверки</b>\n\n"

    for r in results:
        health = r['health']
        if health['status'] == 'healthy':
            text += f"✅ <b>{r['phone']}</b>\n"
            text += f"   Username: @{health.get('username', 'нет')}\n"
            text += f"   Premium: {'Да' if health.get('premium') else 'Нет'}\n"
        else:
            text += f"❌ <b>{r['phone']}</b>\n"
            text += f"   {health.get('message', 'Ошибка')}\n"
        text += "\n"

    await msg.edit_text(
        text,
        reply_markup=back_button("menu_accounts"),
        parse_mode="HTML"
    )

# === УПРАВЛЕНИЕ СЕССИЯМИ ===

@router.callback_query(F.data == "accounts_sessions")
async def accounts_sessions_menu(callback: CallbackQuery):
    """Меню управления сессиями"""
    from keyboards import InlineKeyboardBuilder, InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить чужие сессии (все аккаунты)", callback_data="sessions_clean_all")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="menu_accounts")
    )

    text = """
🧹 <b>Управление сессиями</b>

Здесь вы можете управлять активными сессиями аккаунтов.

<b>Функции:</b>
• Удаление всех других сессий (кроме текущей) со всех аккаунтов
• Защита от несанкционированного доступа

Выберите действие:
"""

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "sessions_clean_all")
async def sessions_clean_all(callback: CallbackQuery):
    """Удалить чужие сессии со всех аккаунтов"""
    await callback.answer("⏳ Очистка сессий...", show_alert=False)

    accounts = await db.get_all_accounts(status='active')

    if not accounts:
        await callback.message.edit_text(
            "❌ Нет активных аккаунтов.",
            reply_markup=back_button("accounts_sessions")
        )
        return

    msg = await callback.message.edit_text(
        f"🧹 Очистка сессий для {len(accounts)} аккаунтов..."
    )

    success = 0
    failed = 0

    for acc in accounts:
        result = await account_manager.terminate_all_other_sessions(acc['id'])
        if result:
            success += 1
        else:
            failed += 1

    text = f"""
✅ <b>Очистка завершена!</b>

Успешно: {success}
Ошибок: {failed}
"""

    await msg.edit_text(
        text,
        reply_markup=back_button("accounts_sessions"),
        parse_mode="HTML"
    )
