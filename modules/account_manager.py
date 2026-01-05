import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl import functions
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError,
    FloodWaitError, AuthKeyUnregisteredError, UserDeactivatedError
)
import config
from database import Database
from typing import Optional, Dict, List
import asyncio

class AccountManager:
    """Управление аккаунтами юзерботов"""

    def __init__(self, db: Database):
        self.db = db
        self.active_clients: Dict[int, TelegramClient] = {}

    def get_session_path(self, session_name: str) -> str:
        """Получить путь к файлу сессии"""
        return os.path.join(config.SESSIONS_DIR, f"{session_name}.session")

    async def add_new_account(self, phone: str) -> Dict[str, any]:
        """Добавить новый аккаунт через авторизацию"""
        session_name = f"account_{phone.replace('+', '')}"
        session_path = self.get_session_path(session_name)

        client = TelegramClient(session_path, config.API_ID, config.API_HASH)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                # Отправляем код
                await client.send_code_request(phone)
                return {
                    'status': 'code_sent',
                    'phone': phone,
                    'session_name': session_name,
                    'message': 'Код отправлен на номер'
                }
            else:
                # Уже авторизован
                account_id = await self.db.add_account(phone, session_name)
                return {
                    'status': 'success',
                    'account_id': account_id,
                    'message': 'Аккаунт уже авторизован'
                }

        except FloodWaitError as e:
            return {
                'status': 'error',
                'message': f'Слишком много попыток. Подождите {e.seconds} секунд'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Ошибка: {str(e)}'
            }
        finally:
            await client.disconnect()

    async def verify_code(self, phone: str, code: str, password: Optional[str] = None) -> Dict[str, any]:
        """Подтвердить код и завершить авторизацию"""
        session_name = f"account_{phone.replace('+', '')}"
        session_path = self.get_session_path(session_name)

        client = TelegramClient(session_path, config.API_ID, config.API_HASH)

        try:
            await client.connect()

            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                else:
                    return {
                        'status': 'password_required',
                        'message': 'Требуется двухфакторная аутентификация'
                    }

            # Успешная авторизация
            account_id = await self.db.add_account(phone, session_name)
            return {
                'status': 'success',
                'account_id': account_id,
                'message': 'Аккаунт успешно добавлен'
            }

        except PhoneCodeInvalidError:
            return {
                'status': 'error',
                'message': 'Неверный код'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Ошибка: {str(e)}'
            }
        finally:
            await client.disconnect()

    async def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """Получить клиент для аккаунта"""
        # Если клиент уже активен
        if account_id in self.active_clients:
            return self.active_clients[account_id]

        # Создаем новый клиент
        account = await self.db.get_account_by_id(account_id)
        if not account:
            return None

        session_path = self.get_session_path(account['session_name'])
        client = TelegramClient(session_path, config.API_ID, config.API_HASH)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                await self.db.update_account_status(
                    account_id,
                    'unauthorized',
                    'Требуется повторная авторизация'
                )
                return None

            # Проверяем на блокировку
            try:
                me = await client.get_me()
                if not me:
                    raise Exception("Аккаунт заблокирован")
            except (AuthKeyUnregisteredError, UserDeactivatedError):
                await self.db.update_account_status(
                    account_id,
                    'banned',
                    'Аккаунт заблокирован или деактивирован'
                )
                return None

            self.active_clients[account_id] = client
            await self.db.update_account_status(account_id, 'active')
            return client

        except Exception as e:
            await self.db.update_account_status(account_id, 'error', str(e))
            return None

    async def disconnect_client(self, account_id: int):
        """Отключить клиент"""
        if account_id in self.active_clients:
            await self.active_clients[account_id].disconnect()
            del self.active_clients[account_id]

    async def disconnect_all(self):
        """Отключить все клиенты"""
        for account_id in list(self.active_clients.keys()):
            await self.disconnect_client(account_id)

    async def check_account_health(self, account_id: int) -> Dict[str, any]:
        """Проверить состояние аккаунта"""
        client = await self.get_client(account_id)
        if not client:
            return {'status': 'error', 'message': 'Не удалось подключиться'}

        try:
            me = await client.get_me()
            dialogs = await client.get_dialogs(limit=1)

            return {
                'status': 'healthy',
                'username': me.username,
                'first_name': me.first_name,
                'phone': me.phone,
                'premium': me.premium or False
            }

        except FloodWaitError as e:
            return {
                'status': 'flood_wait',
                'message': f'Флуд-контроль: {e.seconds} сек'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }

    async def delete_account(self, account_id: int) -> bool:
        """Удалить аккаунт и его сессию"""
        account = await self.db.get_account_by_id(account_id)
        if not account:
            return False

        # Отключаем клиент если активен
        await self.disconnect_client(account_id)

        # Удаляем файл сессии
        session_path = self.get_session_path(account['session_name'])
        try:
            if os.path.exists(session_path):
                os.remove(session_path)
            # Удаляем и journal файл
            journal_path = f"{session_path}-journal"
            if os.path.exists(journal_path):
                os.remove(journal_path)
        except Exception as e:
            print(f"Ошибка удаления файлов сессии: {e}")

        # Удаляем из БД
        await self.db.delete_account(account_id)
        return True

    async def get_account_sessions_info(self, account_id: int) -> List[Dict]:
        """Получить информацию о сессиях аккаунта"""
        client = await self.get_client(account_id)
        if not client:
            return []

        try:
            # Получаем активные сессии
            authorizations = await client(functions.account.GetAuthorizationsRequest())

            sessions = []
            for auth in authorizations.authorizations:
                sessions.append({
                    'hash': auth.hash,
                    'device': auth.device_model,
                    'platform': auth.platform,
                    'location': f"{auth.country}, {auth.region}",
                    'ip': auth.ip,
                    'date': auth.date_created,
                    'active': auth.date_active
                })

            return sessions

        except Exception as e:
            print(f"Ошибка получения сессий: {e}")
            return []

    async def terminate_session(self, account_id: int, session_hash: int) -> bool:
        """Удалить сессию аккаунта"""
        client = await self.get_client(account_id)
        if not client:
            return False

        try:
            from telethon.tl import functions
            await client(functions.account.ResetAuthorizationRequest(hash=session_hash))
            return True
        except Exception as e:
            print(f"Ошибка удаления сессии: {e}")
            return False

    async def terminate_all_other_sessions(self, account_id: int) -> bool:
        """Удалить все другие сессии (кроме текущей)"""
        client = await self.get_client(account_id)
        if not client:
            return False

        try:
            from telethon.tl import functions
            await client(functions.account.ResetAuthorizationsRequest())
            return True
        except Exception as e:
            print(f"Ошибка удаления сессий: {e}")
            return False
