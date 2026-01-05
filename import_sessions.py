#!/usr/bin/env python3
"""
Скрипт для импорта существующих сессий из папки sessions в базу данных
"""
import asyncio
import os
from telethon import TelegramClient
from telethon.errors import AuthKeyUnregisteredError, UserDeactivatedError
import config
from database import Database

async def import_sessions():
    """Импортировать все сессии из папки sessions"""
    db = Database()
    await db.init_db()

    sessions_dir = config.SESSIONS_DIR

    if not os.path.exists(sessions_dir):
        print(f"❌ Папка {sessions_dir} не найдена!")
        return

    # Получаем все .session файлы
    session_files = [f for f in os.listdir(sessions_dir) if f.endswith('.session')]

    if not session_files:
        print(f"❌ В папке {sessions_dir} нет файлов сессий (.session)")
        return

    print(f"🔍 Найдено {len(session_files)} файлов сессий")
    print("=" * 50)

    imported = 0
    skipped = 0
    errors = 0

    for session_file in session_files:
        session_name = session_file.replace('.session', '')
        session_path = os.path.join(sessions_dir, session_name + '.session')

        print(f"\n📋 Обработка: {session_name}")

        try:
            # Создаем клиент
            client = TelegramClient(session_path, config.API_ID, config.API_HASH)
            await client.connect()

            # Проверяем авторизацию
            if not await client.is_user_authorized():
                print(f"  ⚠️  Пропущен: требуется авторизация")
                await client.disconnect()
                skipped += 1
                continue

            # Получаем информацию об аккаунте
            try:
                me = await client.get_me()

                if not me:
                    print(f"  ⚠️  Пропущен: не удалось получить информацию")
                    await client.disconnect()
                    skipped += 1
                    continue

                phone = me.phone or "unknown"
                username = me.username or "без username"
                first_name = me.first_name or ""

                # Проверяем, есть ли уже в БД
                all_accounts = await db.get_all_accounts()
                existing = False
                for acc in all_accounts:
                    if acc.get('phone') == phone or acc.get('session_name') == session_name:
                        existing = True
                        break

                if existing:
                    print(f"  ⏭️  Уже в БД: {phone} (@{username})")
                    await client.disconnect()
                    skipped += 1
                    continue

                # Добавляем в БД
                account_id = await db.add_account(phone, session_name)
                await db.update_account_status(account_id, 'active')

                print(f"  ✅ Импортирован: {phone} (@{username}) - {first_name}")
                imported += 1

            except (AuthKeyUnregisteredError, UserDeactivatedError):
                print(f"  ❌ Ошибка: аккаунт заблокирован или деактивирован")
                errors += 1
            except Exception as e:
                print(f"  ❌ Ошибка: {str(e)}")
                errors += 1
            finally:
                await client.disconnect()

        except Exception as e:
            print(f"  ❌ Ошибка подключения: {str(e)}")
            errors += 1

    print("\n" + "=" * 50)
    print(f"\n📊 Итоги импорта:")
    print(f"  ✅ Импортировано: {imported}")
    print(f"  ⏭️  Пропущено: {skipped}")
    print(f"  ❌ Ошибок: {errors}")
    print(f"  📋 Всего обработано: {len(session_files)}")

    # Показываем все аккаунты в БД
    all_accounts = await db.get_all_accounts()
    print(f"\n📱 Всего аккаунтов в БД: {len(all_accounts)}")

    if all_accounts:
        print("\n📋 Список аккаунтов:")
        for acc in all_accounts:
            status_emoji = {
                'active': '✅',
                'inactive': '⏸️',
                'banned': '🚫',
                'error': '❌',
                'unauthorized': '🔐'
            }.get(acc.get('status', 'inactive'), '❓')

            print(f"  {status_emoji} {acc.get('phone', 'N/A')} - {acc.get('session_name', 'N/A')} ({acc.get('status', 'N/A')})")

if __name__ == "__main__":
    print("🚀 Импорт сессий в базу данных\n")

    # Проверяем настройки
    if not config.API_ID or not config.API_HASH:
        print("❌ Ошибка: API_ID и API_HASH не настроены в config.py")
        exit(1)

    try:
        asyncio.run(import_sessions())
    except KeyboardInterrupt:
        print("\n\n⚠️ Импорт прерван пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
