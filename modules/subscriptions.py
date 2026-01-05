import asyncio
import random
from typing import List, Dict
from telethon.tl import functions
from telethon.errors import FloodWaitError, ChannelPrivateError
from modules.account_manager import AccountManager

async def subscribe_to_channels(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Подписка на каналы

    config:
    - channels: список ссылок на каналы
    - delay_min: минимальная задержка между подписками
    - delay_max: максимальная задержка между подписками
    """
    results = []
    channels = config.get('channels', [])
    delay_min = config.get('delay_min', 2)
    delay_max = config.get('delay_max', 5)

    if not channels:
        return [{'error': 'Нет каналов для подписки'}]

    for account_id in account_ids:
        if stop_flag.is_set():
            break

        result = {
            'account_id': account_id,
            'subscribed': 0,
            'success': False,
            'error': None
        }

        try:
            client = await account_manager.get_client(account_id)
            if not client:
                result['error'] = 'Не удалось подключиться к аккаунту'
                results.append(result)
                continue

            # Подписываемся на каждый канал
            for channel_link in channels:
                if stop_flag.is_set():
                    break

                try:
                    await client(functions.channels.JoinChannelRequest(channel_link))
                    result['subscribed'] += 1

                    # Задержка между подписками
                    await asyncio.sleep(random.uniform(delay_min, delay_max))

                except ChannelPrivateError:
                    result['error'] = f'Канал {channel_link} приватный'

                except FloodWaitError as e:
                    result['error'] = f'Флуд-контроль: {e.seconds} сек'
                    break

                except Exception as e:
                    result['error'] = f'Ошибка подписки на {channel_link}: {str(e)}'

            result['success'] = result['subscribed'] > 0

        except FloodWaitError as e:
            result['error'] = f'Флуд-контроль: {e.seconds} сек'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(2, 4))

    return results
