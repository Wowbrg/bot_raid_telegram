import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
import json
import os
import config

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица админов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    added_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_super_admin INTEGER DEFAULT 0
                )
            """)

            # Таблица аккаунтов
            await db.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE NOT NULL,
                    session_name TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
            """)

            # Таблица задач
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    config TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    accounts_used TEXT,
                    results TEXT
                )
            """)

            # Таблица шаблонов сообщений
            await db.execute("""
                CREATE TABLE IF NOT EXISTS message_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица настроек
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Таблица настроек скорости для действий
            await db.execute("""
                CREATE TABLE IF NOT EXISTS speed_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    delay_min REAL DEFAULT 1.0,
                    delay_max REAL DEFAULT 3.0,
                    message_delay_min REAL DEFAULT 5.0,
                    message_delay_max REAL DEFAULT 15.0,
                    account_delay_min REAL DEFAULT 2.0,
                    account_delay_max REAL DEFAULT 5.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(action_type)
                )
            """)

            await db.commit()

    # === АККАУНТЫ ===

    async def add_account(self, phone: str, session_name: str) -> int:
        """Добавить новый аккаунт"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO accounts (phone, session_name) VALUES (?, ?)",
                (phone, session_name)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_all_accounts(self, status: Optional[str] = None) -> List[Dict]:
        """Получить все аккаунты"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute(
                    "SELECT * FROM accounts WHERE status = ? ORDER BY id",
                    (status,)
                )
            else:
                cursor = await db.execute("SELECT * FROM accounts ORDER BY id")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_account_by_id(self, account_id: int) -> Optional[Dict]:
        """Получить аккаунт по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM accounts WHERE id = ?",
                (account_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_account_status(self, account_id: int, status: str, error: Optional[str] = None):
        """Обновить статус аккаунта"""
        async with aiosqlite.connect(self.db_path) as db:
            if error:
                await db.execute(
                    """UPDATE accounts
                       SET status = ?, last_error = ?, error_count = error_count + 1, last_used = ?
                       WHERE id = ?""",
                    (status, error, datetime.now().isoformat(), account_id)
                )
            elif error is None and status == 'active':
                # При установке статуса 'active' очищаем ошибки
                await db.execute(
                    """UPDATE accounts
                       SET status = ?, last_error = NULL, error_count = 0, last_used = ?
                       WHERE id = ?""",
                    (status, datetime.now().isoformat(), account_id)
                )
            else:
                await db.execute(
                    "UPDATE accounts SET status = ?, last_used = ? WHERE id = ?",
                    (status, datetime.now().isoformat(), account_id)
                )
            await db.commit()

    async def update_account_session_name(self, account_id: int, session_name: str):
        """Обновить имя сессии аккаунта"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE accounts SET session_name = ? WHERE id = ?",
                (session_name, account_id)
            )
            await db.commit()

    async def delete_account(self, account_id: int):
        """Удалить аккаунт"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            await db.commit()

    # === ЗАДАЧИ ===

    async def create_task(self, task_type: str, config: str, accounts_used: str) -> int:
        """Создать новую задачу"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO tasks (task_type, config, accounts_used, started_at)
                   VALUES (?, ?, ?, ?)""",
                (task_type, config, accounts_used, datetime.now().isoformat())
            )
            await db.commit()
            return cursor.lastrowid

    async def get_active_tasks(self) -> List[Dict]:
        """Получить активные задачи"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE status IN ('pending', 'running') ORDER BY id DESC"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_task_by_id(self, task_id: int) -> Optional[Dict]:
        """Получить задачу по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_task_status(self, task_id: int, status: str, results: Optional[str] = None):
        """Обновить статус задачи"""
        async with aiosqlite.connect(self.db_path) as db:
            if status == 'completed' or status == 'failed':
                await db.execute(
                    """UPDATE tasks
                       SET status = ?, results = ?, finished_at = ?
                       WHERE id = ?""",
                    (status, results, datetime.now().isoformat(), task_id)
                )
            else:
                await db.execute(
                    "UPDATE tasks SET status = ? WHERE id = ?",
                    (status, task_id)
                )
            await db.commit()

    async def delete_task(self, task_id: int):
        """Удалить задачу"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await db.commit()

    # === ШАБЛОНЫ СООБЩЕНИЙ ===

    async def add_template(self, name: str, content: str) -> int:
        """Добавить шаблон сообщения"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO message_templates (name, content) VALUES (?, ?)",
                (name, content)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_all_templates(self) -> List[Dict]:
        """Получить все шаблоны"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM message_templates ORDER BY id")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_template(self, template_id: int):
        """Удалить шаблон"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
            await db.commit()

    async def load_system_templates(self, templates_file: str = "templates.json") -> int:
        """Загрузить системные шаблоны из JSON файла"""
        # Проверяем существование файла
        if not os.path.exists(templates_file):
            return 0

        # Читаем файл
        try:
            with open(templates_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Ошибка чтения файла шаблонов: {e}")
            return 0

        # Проверяем наличие ключа messages
        if 'messages' not in data:
            return 0

        messages = data['messages']
        loaded_count = 0

        # Загружаем шаблоны
        async with aiosqlite.connect(self.db_path) as db:
            for idx, content in enumerate(messages, start=1):
                if not content or not isinstance(content, str):
                    continue

                # Генерируем название шаблона
                name = f"Шаблон {idx}"

                # Проверяем, существует ли уже шаблон с таким содержимым
                cursor = await db.execute(
                    "SELECT id FROM message_templates WHERE content = ?",
                    (content,)
                )
                existing = await cursor.fetchone()

                # Если шаблон с таким содержимым не существует, добавляем
                if not existing:
                    await db.execute(
                        "INSERT INTO message_templates (name, content) VALUES (?, ?)",
                        (name, content)
                    )
                    loaded_count += 1

            await db.commit()

        return loaded_count

    # === НАСТРОЙКИ ===

    async def set_setting(self, key: str, value: str):
        """Установить настройку"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            await db.commit()

    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Получить настройку"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else default

    # === НАСТРОЙКИ СКОРОСТИ ===

    async def get_speed_settings(self, action_type: str) -> Optional[Dict]:
        """Получить настройки скорости для действия"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM speed_settings WHERE action_type = ?",
                (action_type,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def set_speed_settings(
        self,
        action_type: str,
        delay_min: float = 1.0,
        delay_max: float = 3.0,
        message_delay_min: float = 5.0,
        message_delay_max: float = 15.0,
        account_delay_min: float = 2.0,
        account_delay_max: float = 5.0
    ):
        """Установить настройки скорости для действия"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO speed_settings
                   (action_type, delay_min, delay_max, message_delay_min, message_delay_max,
                    account_delay_min, account_delay_max)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (action_type, delay_min, delay_max, message_delay_min, message_delay_max,
                 account_delay_min, account_delay_max)
            )
            await db.commit()

    async def get_all_speed_settings(self) -> List[Dict]:
        """Получить все настройки скорости"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM speed_settings ORDER BY action_type")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_speed_settings(self, action_type: str):
        """Удалить настройки скорости"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM speed_settings WHERE action_type = ?", (action_type,))
            await db.commit()

    # === АДМИНЫ ===

    async def add_admin(self, user_id: int, username: Optional[str] = None,
                       first_name: Optional[str] = None, added_by: Optional[int] = None,
                       is_super_admin: bool = False) -> bool:
        """Добавить админа"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """INSERT INTO admins (user_id, username, first_name, added_by, is_super_admin)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, username, first_name, added_by, 1 if is_super_admin else 0)
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_admin(self, user_id: int) -> bool:
        """Удалить админа"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def get_admin(self, user_id: int) -> Optional[Dict]:
        """Получить информацию об админе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM admins WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_all_admins(self) -> List[Dict]:
        """Получить всех админов"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM admins ORDER BY created_at")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь админом"""
        admin = await self.get_admin(user_id)
        return admin is not None

    async def is_super_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь супер-админом"""
        admin = await self.get_admin(user_id)
        return admin is not None and admin['is_super_admin'] == 1
