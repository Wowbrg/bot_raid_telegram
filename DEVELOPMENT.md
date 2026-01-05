# 🛠 Руководство разработчика

## Добавление новых функций

### 1. Создание нового модуля действия

Создайте файл `modules/your_action.py`:

```python
import asyncio
from typing import List, Dict
from modules.account_manager import AccountManager

async def your_action(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Описание вашего действия

    config:
    - param1: описание параметра
    - param2: описание параметра
    """
    results = []

    for account_id in account_ids:
        if stop_flag.is_set():
            break

        result = {
            'account_id': account_id,
            'success': False,
            'error': None
        }

        try:
            client = await account_manager.get_client(account_id)
            if not client:
                result['error'] = 'Не удалось подключиться'
                results.append(result)
                continue

            # Ваша логика здесь
            # ...

            result['success'] = True

        except Exception as e:
            result['error'] = str(e)

        results.append(result)
        await asyncio.sleep(1)  # Задержка

    return results
```

### 2. Регистрация в TaskManager

Добавьте в `modules/task_manager.py`, в метод `_run_task`:

```python
elif task_type == 'your_action':
    from modules.your_action import your_action
    results = await your_action(
        self.account_manager,
        account_ids,
        config,
        stop_flag
    )
```

### 3. Добавление кнопки в меню

В `keyboards.py`, в функцию `actions_menu_kb()`:

```python
builder.row(
    InlineKeyboardButton(text="✨ Ваше действие", callback_data="action_your")
)
```

### 4. Создание обработчика

В `handlers/actions_handlers.py`:

```python
@router.callback_query(F.data == "action_your")
async def action_your(callback: CallbackQuery, state: FSMContext):
    """Ваше действие"""
    await state.update_data(action_type='your_action')

    accounts = await db.get_all_accounts(status='active')
    if not accounts:
        await callback.answer("❌ Нет активных аккаунтов", show_alert=True)
        return

    text = """
✨ <b>Ваше действие</b>

Сколько аккаунтов использовать?
"""

    await callback.message.edit_text(
        text,
        reply_markup=select_accounts_kb(len(accounts)),
        parse_mode="HTML"
    )
    await callback.answer()

async def configure_your_action(callback: CallbackQuery, state: FSMContext):
    """Настройка вашего действия"""
    text = """
✨ <b>Настройка</b>

Введите параметры в формате:
<code>параметр1 | параметр2</code>
"""

    await callback.message.edit_text(
        text,
        reply_markup=cancel_button(),
        parse_mode="HTML"
    )
    await state.set_state(ActionStates.configure)
    await callback.answer()
```

### 5. Обработка конфигурации

Добавьте в обработчик `process_configure`:

```python
if action_type == 'your_action':
    parts = [p.strip() for p in message.text.split('|')]

    config = {
        'param1': parts[0],
        'param2': parts[1] if len(parts) > 1 else 'default',
    }

    await state.update_data(config=config)
    await show_confirmation(message, state)
```

## Структура базы данных

### Таблицы

**accounts** - Аккаунты юзерботов
- id: INTEGER PRIMARY KEY
- phone: TEXT (номер телефона)
- session_name: TEXT (имя файла сессии)
- status: TEXT (active/inactive/banned/error/unauthorized)
- created_at: TIMESTAMP
- last_used: TIMESTAMP
- error_count: INTEGER
- last_error: TEXT

**tasks** - Задачи
- id: INTEGER PRIMARY KEY
- task_type: TEXT (тип задачи)
- status: TEXT (pending/running/completed/failed/stopped)
- config: TEXT (JSON конфигурация)
- created_at: TIMESTAMP
- started_at: TIMESTAMP
- finished_at: TIMESTAMP
- accounts_used: TEXT (JSON список ID аккаунтов)
- results: TEXT (JSON результаты)

**message_templates** - Шаблоны сообщений
- id: INTEGER PRIMARY KEY
- name: TEXT
- content: TEXT
- created_at: TIMESTAMP

**settings** - Настройки
- key: TEXT PRIMARY KEY
- value: TEXT

## Обработка ошибок

### Типичные ошибки Telegram

```python
from telethon.errors import (
    FloodWaitError,      # Флуд-контроль
    ChatWriteForbiddenError,  # Нет прав писать
    ChannelPrivateError, # Канал приватный
    UserDeactivatedError,  # Аккаунт деактивирован
    AuthKeyUnregisteredError  # Сессия невалидна
)

try:
    # Ваш код
    pass
except FloodWaitError as e:
    await asyncio.sleep(e.seconds)
except ChatWriteForbiddenError:
    # Обработка
    pass
```

### Обновление статуса аккаунта

```python
# При ошибке
await db.update_account_status(
    account_id,
    'error',
    f'Описание ошибки: {str(e)}'
)

# При успехе
await db.update_account_status(
    account_id,
    'active'
)
```

## Логирование

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Информация")
logger.warning("Предупреждение")
logger.error("Ошибка")
```

## Тестирование

### Тестирование модуля

```python
import asyncio
from database import Database
from modules.account_manager import AccountManager
from modules.your_action import your_action

async def test():
    db = Database()
    await db.init_db()

    account_manager = AccountManager(db)

    # Тестовая конфигурация
    config = {
        'param1': 'value1',
        'param2': 'value2'
    }

    # Получаем аккаунты
    accounts = await db.get_all_accounts(status='active')
    account_ids = [acc['id'] for acc in accounts[:1]]  # Первый аккаунт

    # Запускаем
    stop_flag = asyncio.Event()
    results = await your_action(
        account_manager,
        account_ids,
        config,
        stop_flag
    )

    print(results)

    await account_manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(test())
```

## Полезные методы

### AccountManager

```python
# Получить клиент
client = await account_manager.get_client(account_id)

# Проверка здоровья
health = await account_manager.check_account_health(account_id)

# Удалить аккаунт
await account_manager.delete_account(account_id)

# Отключить клиент
await account_manager.disconnect_client(account_id)
```

### Database

```python
# Получить все аккаунты
accounts = await db.get_all_accounts()
active = await db.get_all_accounts(status='active')

# Получить аккаунт
account = await db.get_account_by_id(account_id)

# Создать задачу
task_id = await db.create_task(
    task_type='your_action',
    config=json.dumps(config),
    accounts_used=json.dumps(account_ids)
)

# Обновить статус задачи
await db.update_task_status(task_id, 'completed', results_json)
```

### Telethon клиент

```python
# Отправить сообщение
await client.send_message('username', 'Текст')

# Получить entity
entity = await client.get_entity('username_or_link')

# Войти в канал
from telethon.tl import functions
await client(functions.channels.JoinChannelRequest(channel))

# Выйти из канала
await client(functions.channels.LeaveChannelRequest(channel))

# Получить диалоги
dialogs = await client.get_dialogs()

# Получить информацию о себе
me = await client.get_me()
```

## Best Practices

1. **Всегда используйте try/except** для Telegram операций
2. **Добавляйте задержки** между действиями (random.uniform)
3. **Проверяйте stop_flag** в циклах
4. **Логируйте ошибки** для отладки
5. **Обновляйте статусы** аккаунтов и задач
6. **Используйте type hints** для читаемости
7. **Документируйте функции** (docstrings)
8. **Обрабатывайте FloodWait** корректно

## Дополнительные возможности

### Работа с файлами

```python
# Отправка файла
await client.send_file(entity, '/path/to/file.jpg', caption='Описание')

# Загрузка файла
await client.download_media(message, '/path/to/save/')
```

### Работа с реакциями

```python
from telethon.tl import types

await client(functions.messages.SendReactionRequest(
    peer=entity,
    msg_id=message_id,
    reaction=[types.ReactionEmoji(emoticon='👍')]
))
```

### Форвард сообщений

```python
await client.forward_messages(
    entity=target,
    messages=message_ids,
    from_peer=source
)
```

## Расширение базы данных

### Добавление новой таблицы

В `database.py`, в методе `init_db`:

```python
await db.execute("""
    CREATE TABLE IF NOT EXISTS your_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field1 TEXT,
        field2 INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
```

### Добавление методов

```python
async def add_your_record(self, field1: str, field2: int) -> int:
    """Добавить запись"""
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            "INSERT INTO your_table (field1, field2) VALUES (?, ?)",
            (field1, field2)
        )
        await db.commit()
        return cursor.lastrowid

async def get_your_records(self) -> List[Dict]:
    """Получить все записи"""
    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM your_table")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

---

**Удачи в разработке!** 🚀
