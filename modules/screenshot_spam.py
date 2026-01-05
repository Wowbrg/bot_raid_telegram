import asyncio
import random
from typing import List, Dict
from telethon.tl import functions, types
from telethon.errors import FloodWaitError
from modules.account_manager import AccountManager

async def send_screenshot_notifications(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Отправка скриншот-уведомлений пользователю

    config:
    - username: юзернейм или ID пользователя
    - count: количество уведомлений от каждого аккаунта
    - delay_min: минимальная задержка между уведомлениями (сек)
    - delay_max: максимальная задержка между уведомлениями (сек)
    """
    results = []
    username = config.get('username')
    count = config.get('count', 1)
    delay_min = config.get('delay_min', 0.5)
    delay_max = config.get('delay_max', 2)

    for account_id in account_ids:
        if stop_flag.is_set():
            break

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
                results.append(result)
                continue

            # Получаем entity пользователя
            try:
                peer = await client.get_input_entity(username)
            except Exception as e:
                result['error'] = f'Пользователь не найден: {str(e)}'
                results.append(result)
                continue

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
                    if i < count - 1:
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

        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(1, 3))

    return results
