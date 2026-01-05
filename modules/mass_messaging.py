import asyncio
import random
from typing import List, Dict
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
from modules.account_manager import AccountManager

async def send_mass_messages(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Массовая отправка сообщений в группу

    config:
    - group_link: ссылка на группу
    - messages: список сообщений для отправки
    - message_count: количество сообщений от каждого аккаунта
    - delay_min: минимальная задержка между сообщениями
    - delay_max: максимальная задержка между сообщениями
    """
    results = []
    group_link = config.get('group_link')
    messages = config.get('messages', [])
    message_count = config.get('message_count', len(messages))
    delay_min = config.get('delay_min', 5)
    delay_max = config.get('delay_max', 15)

    if not messages:
        return [{'error': 'Нет сообщений для отправки'}]

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

            # Получаем entity группы
            try:
                entity = await client.get_entity(group_link)
            except Exception as e:
                result['error'] = f'Группа не найдена: {str(e)}'
                results.append(result)
                continue

            # Отправляем сообщения
            for i in range(message_count):
                if stop_flag.is_set():
                    break

                # Выбираем случайное сообщение из списка
                message = random.choice(messages)

                try:
                    await client.send_message(entity, message)
                    result['sent'] += 1

                    # Задержка между сообщениями
                    if i < message_count - 1:
                        await asyncio.sleep(random.uniform(delay_min, delay_max))

                except FloodWaitError as e:
                    result['error'] = f'Флуд-контроль: {e.seconds} сек'
                    break

                except ChatWriteForbiddenError:
                    result['error'] = 'Нет прав на отправку сообщений в чате'
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
            await asyncio.sleep(random.uniform(3, 7))

    return results
