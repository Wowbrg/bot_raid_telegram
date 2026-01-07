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
                sent_code = await client.send_code_request(phone)
                return {
                    'status': 'code_sent',
                    'phone': phone,
                    'session_name': session_name,
                    'phone_code_hash': sent_code.phone_code_hash,
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

    async def verify_code(self, phone: str, code: str, phone_code_hash: str, password: Optional[str] = None) -> Dict[str, any]:
        """Подтвердить код и завершить авторизацию"""
        temp_session_name = f"account_{phone.replace('+', '')}"
        temp_session_path = self.get_session_path(temp_session_name)

        client = TelegramClient(temp_session_path, config.API_ID, config.API_HASH)

        try:
            await client.connect()

            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                else:
                    return {
                        'status': 'password_required',
                        'message': 'Требуется двухфакторная аутентификация'
                    }

            # Проверяем, не существует ли уже аккаунт с таким номером
            all_accounts = await self.db.get_all_accounts()
            existing_account = None
            for acc in all_accounts:
                if acc['phone'] == phone:
                    existing_account = acc
                    break

            if existing_account:
                # Аккаунт уже существует - обновляем его
                account_id = existing_account['id']
                # Удаляем старую сессию если она есть
                old_session_path = self.get_session_path(existing_account['session_name'])
                if os.path.exists(old_session_path):
                    try:
                        os.remove(old_session_path)
                        journal_path = f"{old_session_path}-journal"
                        if os.path.exists(journal_path):
                            os.remove(journal_path)
                    except Exception as e:
                        print(f"Предупреждение: не удалось удалить старую сессию: {e}")
            else:
                # Успешная авторизация - добавляем в БД с временным именем
                account_id = await self.db.add_account(phone, temp_session_name)

            # Переименовываем сессию в формат account_{id}
            final_session_name = f"account_{account_id}"
            final_session_path = self.get_session_path(final_session_name)

            # Отключаем клиент перед переименованием
            await client.disconnect()

            # Небольшая задержка для завершения записи сессии
            await asyncio.sleep(0.5)

            # Переименовываем файлы сессии
            try:
                if os.path.exists(temp_session_path):
                    os.rename(temp_session_path, final_session_path)
                # Переименовываем и journal файл если есть
                temp_journal = f"{temp_session_path}-journal"
                final_journal = f"{final_session_path}-journal"
                if os.path.exists(temp_journal):
                    os.rename(temp_journal, final_journal)
            except Exception as e:
                print(f"Предупреждение: не удалось переименовать сессию: {e}")

            # Обновляем имя сессии в БД
            await self.db.update_account_session_name(account_id, final_session_name)

            # Убеждаемся что статус 'active' (по умолчанию он уже active)
            await self.db.update_account_status(account_id, 'active')

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
            # Клиент уже отключен выше при успехе, но на случай ошибки
            try:
                if client.is_connected():
                    await client.disconnect()
            except:
                pass

    async def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """Получить клиент для аккаунта"""
        # Если клиент уже активен
        if account_id in self.active_clients:
            return self.active_clients[account_id]

        # Создаем новый клиент
        account = await self.db.get_account_by_id(account_id)
        if not account:
            return None

        # Не пытаемся подключиться к заблокированным аккаунтам
        if account['status'] == 'banned':
            return None

        # Проверяем существование файла сессии
        session_path = self.get_session_path(account['session_name'])
        if not os.path.exists(session_path):
            await self.db.update_account_status(
                account_id,
                'error',
                'Файл сессии не найден'
            )
            return None

        client = TelegramClient(session_path, config.API_ID, config.API_HASH)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
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
            except (AuthKeyUnregisteredError, UserDeactivatedError) as e:
                await client.disconnect()
                await self.db.update_account_status(
                    account_id,
                    'banned',
                    f'Аккаунт заблокирован: {str(e)}'
                )
                # Удаляем файл сессии заблокированного аккаунта
                try:
                    if os.path.exists(session_path):
                        os.remove(session_path)
                    journal_path = f"{session_path}-journal"
                    if os.path.exists(journal_path):
                        os.remove(journal_path)
                except Exception as remove_err:
                    print(f"Ошибка удаления сессии заблокированного аккаунта: {remove_err}")
                return None

            self.active_clients[account_id] = client
            await self.db.update_account_status(account_id, 'active')
            return client

        except Exception as e:
            try:
                await client.disconnect()
            except:
                pass
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

    async def get_valid_accounts(self, status: Optional[str] = 'active') -> List[Dict]:
        """
        Получить список валидных аккаунтов

        Валидный аккаунт:
        - Имеет файл сессии
        - Не в статусе banned
        - Опционально: имеет указанный статус
        """
        all_accounts = await self.db.get_all_accounts()
        valid_accounts = []

        for account in all_accounts:
            # Пропускаем заблокированные
            if account['status'] == 'banned':
                continue

            # Проверяем статус если указан
            if status and account['status'] != status:
                continue

            # Проверяем существование файла сессии
            session_path = self.get_session_path(account['session_name'])
            if not os.path.exists(session_path):
                # Файл сессии не существует - помечаем как error
                await self.db.update_account_status(
                    account['id'],
                    'error',
                    'Файл сессии не найден'
                )
                continue

            valid_accounts.append(account)

        return valid_accounts

    async def cleanup_invalid_accounts(self) -> Dict[str, any]:
        """
        Очистка недействительных аккаунтов

        Удаляет или помечает:
        - Аккаунты без файлов сессий
        - Аккаунты с временными именами сессий (не переименованные)
        - Аккаунты со статусом banned старше 7 дней
        """
        all_accounts = await self.db.get_all_accounts()

        marked_error = []
        removed_temp = []
        removed_banned = []

        for account in all_accounts:
            session_path = self.get_session_path(account['session_name'])

            # Проверяем, не является ли это временной сессией (содержит номер телефона)
            # Временные сессии имеют формат: account_1234567890
            if account['session_name'].startswith('account_') and len(account['session_name']) > 15:
                # Это похоже на временное имя с номером телефона
                # Удаляем такой аккаунт
                await self.db.delete_account(account['id'])
                removed_temp.append({
                    'id': account['id'],
                    'phone': account['phone'],
                    'session_name': account['session_name']
                })
                # Удаляем файл сессии если есть
                if os.path.exists(session_path):
                    try:
                        os.remove(session_path)
                        journal_path = f"{session_path}-journal"
                        if os.path.exists(journal_path):
                            os.remove(journal_path)
                    except Exception as e:
                        print(f"Ошибка удаления временной сессии: {e}")
                continue

            # Проверяем существование файла сессии
            if not os.path.exists(session_path):
                if account['status'] != 'error':
                    await self.db.update_account_status(
                        account['id'],
                        'error',
                        'Файл сессии не найден'
                    )
                    marked_error.append({
                        'id': account['id'],
                        'phone': account['phone']
                    })

            # Удаляем старые заблокированные аккаунты (опционально)
            # Можно раскомментировать если нужно
            # if account['status'] == 'banned':
            #     removed_banned.append({
            #         'id': account['id'],
            #         'phone': account['phone']
            #     })
            #     await self.delete_account(account['id'])

        return {
            'status': 'success',
            'marked_error': marked_error,
            'removed_temp': removed_temp,
            'removed_banned': removed_banned
        }

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

    async def reactivate_unauthorized_accounts(self) -> Dict[str, any]:
        """
        Попытаться переактивировать аккаунты со статусом 'unauthorized'
        Полезно после перезапуска бота или если сессии восстановились
        """
        accounts = await self.db.get_all_accounts()
        reactivated = []
        failed = []

        for account in accounts:
            # Обрабатываем только unauthorized аккаунты
            if account['status'] != 'unauthorized':
                continue

            # Проверяем существование файла сессии
            session_path = self.get_session_path(account['session_name'])
            if not os.path.exists(session_path):
                failed.append({
                    'id': account['id'],
                    'phone': account['phone'],
                    'error': 'Файл сессии не найден'
                })
                continue

            # Пытаемся подключиться
            try:
                client = TelegramClient(session_path, config.API_ID, config.API_HASH)
                await client.connect()

                if await client.is_user_authorized():
                    # Успешно авторизован - восстанавливаем статус
                    await self.db.update_account_status(account['id'], 'active', error=None)
                    reactivated.append({
                        'id': account['id'],
                        'phone': account['phone']
                    })
                else:
                    failed.append({
                        'id': account['id'],
                        'phone': account['phone'],
                        'error': 'Не авторизован'
                    })

                await client.disconnect()

            except Exception as e:
                failed.append({
                    'id': account['id'],
                    'phone': account['phone'],
                    'error': str(e)
                })
                try:
                    await client.disconnect()
                except:
                    pass

        return {
            'status': 'success',
            'reactivated': reactivated,
            'failed': failed
        }

    async def sync_sessions_with_db(self) -> Dict[str, any]:
        """Синхронизировать файлы сессий с базой данных"""
        if not os.path.exists(config.SESSIONS_DIR):
            return {
                'status': 'error',
                'message': 'Папка сессий не найдена'
            }

        # Получаем все существующие аккаунты из БД
        existing_accounts = await self.db.get_all_accounts()
        existing_sessions = {acc['session_name'] for acc in existing_accounts}

        # Сканируем папку сессий
        session_files = [
            f for f in os.listdir(config.SESSIONS_DIR)
            if f.endswith('.session')
        ]

        added = []
        errors = []
        skipped = []

        for session_file in session_files:
            session_name = session_file.replace('.session', '')

            # Пропускаем, если уже есть в БД
            if session_name in existing_sessions:
                skipped.append(session_name)
                continue

            session_path = self.get_session_path(session_name)
            client = TelegramClient(session_path, config.API_ID, config.API_HASH)

            try:
                await client.connect()

                # Проверяем авторизацию
                if not await client.is_user_authorized():
                    errors.append({
                        'session': session_name,
                        'error': 'Не авторизован'
                    })
                    await client.disconnect()
                    continue

                # Получаем информацию об аккаунте
                me = await client.get_me()
                phone = f"+{me.phone}" if me.phone else "unknown"

                # Проверяем, нет ли уже аккаунта с таким номером
                phone_exists = any(acc['phone'] == phone for acc in existing_accounts)
                if phone_exists:
                    errors.append({
                        'session': session_name,
                        'error': f'Аккаунт с номером {phone} уже существует'
                    })
                    await client.disconnect()
                    continue

                # Добавляем в БД
                account_id = await self.db.add_account(phone, session_name)
                added.append({
                    'id': account_id,
                    'phone': phone,
                    'session': session_name
                })

                await client.disconnect()

            except Exception as e:
                errors.append({
                    'session': session_name,
                    'error': str(e)
                })
                try:
                    await client.disconnect()
                except:
                    pass

        return {
            'status': 'success',
            'added': added,
            'skipped': skipped,
            'errors': errors,
            'total_files': len(session_files)
        }
