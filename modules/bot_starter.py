import asyncio
import random
from typing import List, Dict
from telethon.errors import FloodWaitError
from modules.account_manager import AccountManager

async def start_bots(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Запуск ботов по реферальной ссылке

    config:
    - bot_username: юзернейм бота
    - start_param: параметр для /start (реферальный код)
    - delay_min: минимальная задержка
    - delay_max: максимальная задержка
    """
    results = []
    bot_username = config.get('bot_username')
    start_param = config.get('start_param', '')
    delay_min = config.get('delay_min', 2)
    delay_max = config.get('delay_max', 5)

    if not bot_username:
        return [{'error': 'Не указан юзернейм бота'}]

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

            try:
                # Получаем бота
                bot = await client.get_entity(bot_username)

                # Отправляем /start с параметром
                if start_param:
                    await client.send_message(bot, f'/start {start_param}')
                else:
                    await client.send_message(bot, '/start')

                result['success'] = True

            except Exception as e:
                result['error'] = f'Ошибка запуска бота: {str(e)}'

        except FloodWaitError as e:
            result['error'] = f'Флуд-контроль: {e.seconds} сек'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(delay_min, delay_max))

    return results
