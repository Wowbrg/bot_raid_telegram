import asyncio
import random
from typing import List, Dict
from telethon.tl import functions
from telethon.errors import FloodWaitError, ChannelPrivateError
from modules.account_manager import AccountManager


async def _subscribe_for_account(
    account_manager: AccountManager,
    account_id: int,
    config: Dict,
    stop_flag: asyncio.Event
) -> Dict:
    """Подписка на каналы для одного аккаунта"""
    channels = config.get('channels', [])
    delay_min = config.get('delay_min', 0)
    delay_max = config.get('delay_max', 1)

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
            return result

        # Подписываемся на каждый канал
        for channel_link in channels:
            if stop_flag.is_set():
                break

            try:
                await client(functions.channels.JoinChannelRequest(channel_link))
                result['subscribed'] += 1

                # Задержка между подписками
                if delay_max > 0:
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

    return result


async def subscribe_to_channels(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Подписка на каналы (ПАРАЛЛЕЛЬНО)

    config:
    - channels: список ссылок на каналы
    - delay_min: минимальная задержка между подписками (по умолчанию 0)
    - delay_max: максимальная задержка между подписками (по умолчанию 1)

    ВСЕ АККАУНТЫ РАБОТАЮТ ПАРАЛЛЕЛЬНО!
    """
    channels = config.get('channels', [])
    if not channels:
        return [{'error': 'Нет каналов для подписки'}]

    # Запускаем все аккаунты параллельно
    tasks = [
        _subscribe_for_account(account_manager, account_id, config, stop_flag)
        for account_id in account_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем исключения
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append({
                'account_id': account_ids[i],
                'subscribed': 0,
                'success': False,
                'error': str(result)
            })
        else:
            final_results.append(result)

    return final_results
