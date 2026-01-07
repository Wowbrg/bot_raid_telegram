from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter

from keyboards import templates_menu_kb, template_detail_kb, templates_list_kb, back_button, cancel_button
from database import Database

router = Router()

# Глобальные переменные
db: Database = None

def setup(database: Database):
    """Настройка зависимостей"""
    global db
    db = database

# === STATES ===

class TemplateStates(StatesGroup):
    name = State()
    content = State()

# === МЕНЮ ШАБЛОНОВ ===

@router.callback_query(F.data == "menu_templates")
async def menu_templates(callback: CallbackQuery):
    """Меню шаблонов"""
    await callback.answer()

    templates = await db.get_all_templates()

    text = f"""
📝 <b>Шаблоны сообщений</b>

📊 Всего шаблонов: {len(templates)}

Используйте шаблоны для быстрой настройки рассылок.

Выберите действие:
"""

    await callback.message.edit_text(
        text,
        reply_markup=templates_menu_kb(),
        parse_mode="HTML"
    )

# === СПИСОК ШАБЛОНОВ ===

@router.callback_query(F.data == "templates_list")
async def templates_list(callback: CallbackQuery):
    """Список шаблонов - переход на первую страницу"""
    await callback.answer()
    await show_templates_page(callback, 1)

@router.callback_query(F.data.startswith("templates_page_"))
async def templates_page(callback: CallbackQuery):
    """Навигация по страницам шаблонов"""
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    await show_templates_page(callback, page)

async def show_templates_page(callback: CallbackQuery, page: int):
    """Показать страницу шаблонов"""
    templates = await db.get_all_templates()

    if not templates:
        await callback.message.edit_text(
            "📝 У вас пока нет шаблонов.\n\nСоздайте первый шаблон!",
            reply_markup=back_button("menu_templates")
        )
        return

    # Пагинация
    items_per_page = 10
    total_items = len(templates)
    total_pages = (total_items + items_per_page - 1) // items_per_page

    # Проверка границ страницы
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages

    # Получаем шаблоны для текущей страницы
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    page_templates = templates[start_idx:end_idx]

    # Формируем текст
    text = f"📝 <b>Список шаблонов</b>\n\n"
    text += f"📊 Всего: {total_items} | Страница {page}/{total_pages}\n\n"

    for tpl in page_templates:
        preview = tpl['content'][:50] + "..." if len(tpl['content']) > 50 else tpl['content']
        text += f"📄 <b>{tpl['name']}</b> (ID: {tpl['id']})\n"
        text += f"   {preview}\n\n"

    # Показываем
    await callback.message.edit_text(
        text,
        reply_markup=templates_list_kb(
            page=page,
            total_pages=total_pages,
            has_prev=(page > 1),
            has_next=(page < total_pages)
        ),
        parse_mode="HTML"
    )

# === ДОБАВЛЕНИЕ ШАБЛОНА ===

@router.callback_query(F.data == "templates_add")
async def templates_add(callback: CallbackQuery, state: FSMContext):
    """Добавить шаблон"""
    await callback.answer()

    await callback.message.edit_text(
        "📝 <b>Создание шаблона</b>\n\n"
        "Введите название шаблона:",
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(TemplateStates.name)

@router.message(StateFilter(TemplateStates.name))
async def process_template_name(message: Message, state: FSMContext):
    """Обработка названия"""
    name = message.text.strip()

    if len(name) > 50:
        await message.answer("❌ Название слишком длинное (макс. 50 символов)")
        return

    await state.update_data(name=name)

    try:
        await message.delete()
    except:
        pass

    await message.answer(
        f"📝 Название: <b>{name}</b>\n\n"
        "Теперь отправьте текст шаблона:",
        parse_mode="HTML"
    )
    await state.set_state(TemplateStates.content)

@router.message(StateFilter(TemplateStates.content))
async def process_template_content(message: Message, state: FSMContext):
    """Обработка содержимого"""
    content = message.text.strip()
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    # Сохраняем в БД
    template_id = await db.add_template(data['name'], content)

    await state.clear()

    await message.answer(
        f"✅ Шаблон создан!\n\n"
        f"ID: {template_id}\n"
        f"Название: {data['name']}",
        reply_markup=back_button("menu_templates")
    )

# === УДАЛЕНИЕ ШАБЛОНА ===

@router.callback_query(F.data.startswith("template_delete_"))
async def template_delete(callback: CallbackQuery):
    """Удалить шаблон"""
    await callback.answer()

    template_id = int(callback.data.split("_")[-1])

    await db.delete_template(template_id)

    await callback.message.edit_text(
        "✅ Шаблон удален!",
        reply_markup=back_button("templates_list")
    )
