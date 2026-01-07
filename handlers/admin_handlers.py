from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from keyboards import InlineKeyboardBuilder, InlineKeyboardButton, back_button
from database import Database

router = Router()

# Глобальные переменные для зависимостей
db: Database = None

def setup(database: Database):
    """Настройка зависимостей"""
    global db
    db = database

# === STATES ===

class AddAdminStates(StatesGroup):
    waiting_user_id = State()

# === МЕНЮ АДМИНОВ ===

@router.callback_query(F.data == "menu_admins")
async def menu_admins(callback: CallbackQuery, is_super_admin: bool = False):
    """Меню управления админами (только для супер-админа)"""
    await callback.answer()

    if not is_super_admin:
        await callback.answer("❌ Доступно только для супер-админа", show_alert=True)
        return

    admins = await db.get_all_admins()

    text = f"""
👥 <b>Управление админами</b>

📊 Всего админов: {len(admins)}

Вы можете:
• Добавить нового админа
• Удалить админа
• Просмотреть список админов
"""

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить админа", callback_data="admins_add")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список админов", callback_data="admins_list")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    )

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

# === СПИСОК АДМИНОВ ===

@router.callback_query(F.data == "admins_list")
async def admins_list(callback: CallbackQuery, is_super_admin: bool = False):
    """Список всех админов"""
    await callback.answer()

    if not is_super_admin:
        await callback.answer("❌ Доступно только для супер-админа", show_alert=True)
        return

    admins = await db.get_all_admins()

    if not admins:
        text = "📋 <b>Список админов</b>\n\nПока нет админов."
    else:
        text = "📋 <b>Список админов</b>\n\n"
        for admin in admins:
            status = "👑 Супер-админ" if admin['is_super_admin'] else "👤 Админ"
            username = f"@{admin['username']}" if admin['username'] else admin['first_name']
            text += f"{status}\n"
            text += f"├ ID: <code>{admin['user_id']}</code>\n"
            text += f"├ Имя: {username}\n"
            if admin['added_by']:
                text += f"├ Добавил: <code>{admin['added_by']}</code>\n"
            text += f"└ Добавлен: {admin['created_at'][:10]}\n"

            # Кнопка удаления (кроме супер-админа)
            if not admin['is_super_admin']:
                text += f"   /remove_admin_{admin['user_id']}\n"
            text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=back_button("menu_admins"),
        parse_mode="HTML"
    )

# === ДОБАВЛЕНИЕ АДМИНА ===

@router.callback_query(F.data == "admins_add")
async def admins_add(callback: CallbackQuery, state: FSMContext, is_super_admin: bool = False):
    """Начать добавление админа"""
    await callback.answer()

    if not is_super_admin:
        await callback.answer("❌ Доступно только для супер-админа", show_alert=True)
        return

    await callback.message.edit_text(
        "➕ <b>Добавление нового админа</b>\n\n"
        "Отправьте Telegram ID пользователя, которого хотите сделать админом.\n\n"
        "Чтобы узнать ID пользователя, попросите его написать @userinfobot\n\n"
        "Или отправьте /cancel для отмены.",
        reply_markup=back_button("menu_admins"),
        parse_mode="HTML"
    )
    await state.set_state(AddAdminStates.waiting_user_id)

@router.message(StateFilter(AddAdminStates.waiting_user_id))
async def process_admin_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя для добавления админа"""

    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено")
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Отправьте числовой ID пользователя.")
        return

    # Проверяем, не является ли уже админом
    is_already_admin = await db.is_admin(user_id)
    if is_already_admin:
        await state.clear()
        await message.answer(
            f"⚠️ Пользователь с ID <code>{user_id}</code> уже является админом.",
            parse_mode="HTML"
        )
        return

    # Добавляем админа
    success = await db.add_admin(
        user_id=user_id,
        added_by=message.from_user.id,
        is_super_admin=False
    )

    await state.clear()

    if success:
        await message.answer(
            f"✅ <b>Админ добавлен!</b>\n\n"
            f"User ID: <code>{user_id}</code>\n\n"
            f"Теперь этот пользователь может использовать бота.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ Ошибка при добавлении админа.",
            parse_mode="HTML"
        )

# === УДАЛЕНИЕ АДМИНА ===

@router.message(F.text.regexp(r"/remove_admin_(\d+)"))
async def remove_admin(message: Message, is_super_admin: bool = False):
    """Удалить админа"""

    if not is_super_admin:
        await message.answer("❌ Доступно только для супер-админа")
        return

    user_id = int(message.text.split("_")[-1])

    # Проверяем, не пытается ли удалить супер-админа
    is_super = await db.is_super_admin(user_id)
    if is_super:
        await message.answer("❌ Нельзя удалить супер-админа")
        return

    success = await db.remove_admin(user_id)

    if success:
        await message.answer(
            f"✅ Админ <code>{user_id}</code> удален",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при удалении админа")
