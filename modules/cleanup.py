import asyncio
import random
from typing import List, Dict
from telethon.tl import functions, types
from telethon.errors import FloodWaitError
from modules.account_manager import AccountManager

async def cleanup_accounts(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Очистка аккаунтов от чатов, каналов, переписок

    config:
    - cleanup_chats: очистить чаты (True/False)
    - cleanup_channels: очистить каналы (True/False)
    - cleanup_private: очистить личные переписки (True/False)
    - delete_messages: удалить сообщения в личных чатах (True/False)
    """
    results = []
    cleanup_chats = config.get('cleanup_chats', True)
    cleanup_channels = config.get('cleanup_channels', True)
    cleanup_private = config.get('cleanup_private', False)
    delete_messages = config.get('delete_messages', False)

    for account_id in account_ids:
        if stop_flag.is_set():
            break

        result = {
            'account_id': account_id,
            'chats_left': 0,
            'channels_left': 0,
            'chats_deleted': 0,
            'success': False,
            'error': None
        }

        try:
            client = await account_manager.get_client(account_id)
            if not client:
                result['error'] = 'Не удалось подключиться к аккаунту'
                results.append(result)
                continue

            # Получаем все диалоги
            dialogs = await client.get_dialogs()

            for dialog in dialogs:
                if stop_flag.is_set():
                    break

                try:
                    # Чаты (группы)
                    if dialog.is_group and cleanup_chats:
                        await client(functions.channels.LeaveChannelRequest(dialog.entity))
                        result['chats_left'] += 1
                        await asyncio.sleep(random.uniform(1, 2))

                    # Каналы
                    elif dialog.is_channel and cleanup_channels:
                        await client(functions.channels.LeaveChannelRequest(dialog.entity))
                        result['channels_left'] += 1
                        await asyncio.sleep(random.uniform(1, 2))

                    # Личные переписки
                    elif dialog.is_user and cleanup_private:
                        if delete_messages:
                            # Удаляем все сообщения
                            await client.delete_dialog(dialog.entity)
                        else:
                            # Просто архивируем
                            await client(functions.folders.EditPeerFoldersRequest(
                                folder_peers=[types.InputFolderPeer(
                                    peer=dialog.entity,
                                    folder_id=1
                                )]
                            ))
                        result['chats_deleted'] += 1
                        await asyncio.sleep(random.uniform(0.5, 1))

                except FloodWaitError as e:
                    result['error'] = f'Флуд-контроль: {e.seconds} сек'
                    break

                except Exception as e:
                    # Игнорируем ошибки отдельных чатов
                    continue

            result['success'] = True

        except FloodWaitError as e:
            result['error'] = f'Флуд-контроль: {e.seconds} сек'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

    return results
