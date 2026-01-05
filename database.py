import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict
import config

class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
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
            else:
                await db.execute(
                    "UPDATE accounts SET status = ?, last_used = ? WHERE id = ?",
                    (status, datetime.now().isoformat(), account_id)
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
