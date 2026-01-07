import asyncio
import random
from typing import List, Dict
from telethon.tl import functions, types
from telethon.errors import FloodWaitError
from modules.account_manager import AccountManager

async def _send_screenshot_notifications_for_account(
    account_manager: AccountManager,
    account_id: int,
    config: Dict,
    stop_flag: asyncio.Event
) -> Dict:
    """Отправка скриншот-уведомлений для одного аккаунта"""
    username = config.get('username')
    count = config.get('count', 1)
    delay_min = config.get('delay_min', 0)
    delay_max = config.get('delay_max', 0.5)

    result = {
        'account_id': account_id,
        'sent': 0,
        'success': False,
        'error': None
    }

    try:
        client = await account_manager.get_client(account_id)
        if not client:
            result['error'] = 'Не удалось подключиться к аккаунту'
            return result

        # Получаем entity пользователя
        try:
            peer = await client.get_input_entity(username)
        except Exception as e:
            result['error'] = f'Пользователь не найден: {str(e)}'
            return result

        # Отправляем уведомления
        for i in range(count):
            if stop_flag.is_set():
                break

            try:
                await client(functions.messages.SendScreenshotNotificationRequest(
                    peer=peer,
                    reply_to=types.InputReplyToMessage(reply_to_msg_id=0)
                ))
                result['sent'] += 1

                # Задержка между уведомлениями
                if i < count - 1 and delay_max > 0:
                    await asyncio.sleep(random.uniform(delay_min, delay_max))

            except FloodWaitError as e:
                result['error'] = f'Флуд-контроль: {e.seconds} сек'
                break

            except Exception as e:
                result['error'] = f'Ошибка отправки: {str(e)}'
                break

        result['success'] = result['sent'] > 0

    except FloodWaitError as e:
        result['error'] = f'Флуд-контроль: {e.seconds} сек'

    except Exception as e:
        result['error'] = str(e)

    return result


async def send_screenshot_notifications(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Отправка скриншот-уведомлений пользователю (ПАРАЛЛЕЛЬНО)

    config:
    - username: юзернейм или ID пользователя
    - count: количество уведомлений от каждого аккаунта
    - delay_min: минимальная задержка между уведомлениями (по умолчанию 0)
    - delay_max: максимальная задержка между уведомлениями (по умолчанию 0.5)

    ВСЕ АККАУНТЫ РАБОТАЮТ ПАРАЛЛЕЛЬНО!
    """
    # Запускаем все аккаунты параллельно
    tasks = [
        _send_screenshot_notifications_for_account(account_manager, account_id, config, stop_flag)
        for account_id in account_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем исключения
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append({
                'account_id': account_ids[i],
                'sent': 0,
                'success': False,
                'error': str(result)
            })
        else:
            final_results.append(result)

    return final_results
