import asyncio
import random
from typing import List, Dict
from telethon.errors import FloodWaitError, ChannelPrivateError, InviteHashExpiredError
from modules.account_manager import AccountManager

async def join_leave_groups(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Вход и выход из группы

    config:
    - group_link: ссылка на группу
    - action: 'join' или 'leave' или 'cycle'
    - cycle_duration: длительность в секундах (для cycle)
    - delay_min: минимальная задержка между действиями
    - delay_max: максимальная задержка между действиями
    """
    results = []
    group_link = config.get('group_link')
    action = config.get('action', 'cycle')
    cycle_duration = config.get('cycle_duration', 3600)  # 1 час по умолчанию
    delay_min = config.get('delay_min', 5)
    delay_max = config.get('delay_max', 15)

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

            if action == 'join':
                # Просто входим в группу
                try:
                    await client(functions.channels.JoinChannelRequest(group_link))
                    result['success'] = True
                    result['action'] = 'joined'
                except Exception as e:
                    result['error'] = f'Ошибка входа: {str(e)}'

            elif action == 'leave':
                # Просто выходим из группы
                try:
                    entity = await client.get_entity(group_link)
                    await client(functions.channels.LeaveChannelRequest(entity))
                    result['success'] = True
                    result['action'] = 'left'
                except Exception as e:
                    result['error'] = f'Ошибка выхода: {str(e)}'

            elif action == 'cycle':
                # Циклично входим и выходим
                start_time = asyncio.get_event_loop().time()
                cycle_count = 0

                while not stop_flag.is_set():
                    # Проверяем время
                    if asyncio.get_event_loop().time() - start_time > cycle_duration:
                        break

                    try:
                        # Входим
                        from telethon.tl import functions
                        await client(functions.channels.JoinChannelRequest(group_link))
                        await asyncio.sleep(random.uniform(delay_min, delay_max))

                        if stop_flag.is_set():
                            break

                        # Выходим
                        entity = await client.get_entity(group_link)
                        await client(functions.channels.LeaveChannelRequest(entity))
                        await asyncio.sleep(random.uniform(delay_min, delay_max))

                        cycle_count += 1

                    except FloodWaitError as e:
                        result['error'] = f'Флуд-контроль: {e.seconds} сек'
                        await asyncio.sleep(e.seconds)
                        break

                    except Exception as e:
                        result['error'] = f'Ошибка цикла: {str(e)}'
                        break

                result['success'] = True
                result['action'] = f'cycled_{cycle_count}_times'

        except FloodWaitError as e:
            result['error'] = f'Флуд-контроль: {e.seconds} сек'

        except ChannelPrivateError:
            result['error'] = 'Канал приватный или недоступен'

        except InviteHashExpiredError:
            result['error'] = 'Ссылка-приглашение истекла'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(2, 5))

    return results
