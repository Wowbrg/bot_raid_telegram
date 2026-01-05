import asyncio
import random
from typing import List, Dict
from telethon.errors import FloodWaitError
from modules.account_manager import AccountManager

async def join_voice_call(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Вступление в голосовой чат и воспроизведение аудио

    config:
    - group_link: ссылка на группу
    - audio_file: путь к аудио файлу (опционально)
    - duration: длительность участия в звонке (секунды)
    """
    results = []
    group_link = config.get('group_link')
    audio_file = config.get('audio_file')
    duration = config.get('duration', 60)

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
                result['error'] = 'Не удалось подключиться к аккаунту'
                results.append(result)
                continue

            # Получаем entity группы
            try:
                entity = await client.get_entity(group_link)
            except Exception as e:
                result['error'] = f'Группа не найдена: {str(e)}'
                results.append(result)
                continue

            # Примечание: для полноценной работы с голосовыми чатами
            # требуется pytgcalls, но это упрощенная версия
            # Здесь можно интегрировать pytgcalls для воспроизведения аудио

            try:
                from telethon.tl import functions
                # Присоединяемся к голосовому чату
                call = await client(functions.phone.JoinGroupCallRequest(
                    call=entity,
                    muted=False,
                    join_as=await client.get_me()
                ))

                result['success'] = True
                result['action'] = 'joined_call'

                # Держим соединение указанное время
                await asyncio.sleep(duration if not stop_flag.is_set() else 0)

                # Выходим из звонка
                await client(functions.phone.LeaveGroupCallRequest(
                    call=entity
                ))

            except Exception as e:
                result['error'] = f'Ошибка подключения к звонку: {str(e)}'

        except FloodWaitError as e:
            result['error'] = f'Флуд-контроль: {e.seconds} сек'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(2, 5))

    return results
