import asyncio
import random
from typing import List, Dict
from telethon.errors import FloodWaitError, ChatWriteForbiddenError
from modules.account_manager import AccountManager

async def _send_messages_for_account(
    account_manager: AccountManager,
    account_id: int,
    config: Dict,
    stop_flag: asyncio.Event
) -> Dict:
    """Отправка сообщений для одного аккаунта"""
    group_link = config.get('group_link')
    messages = config.get('messages', [])
    message_count = config.get('message_count', 100)
    delay_min = config.get('delay_min', 1)
    delay_max = config.get('delay_max', 5)

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

        # Получаем entity группы
        try:
            entity = await client.get_entity(group_link)
        except Exception as e:
            result['error'] = f'Группа не найдена: {str(e)}'
            return result

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
                if i < message_count - 1 and delay_max > 0:
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

    return result


async def send_mass_messages(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Массовая отправка сообщений в группу (ПАРАЛЛЕЛЬНО)

    config:
    - group_link: ссылка на группу
    - messages: список сообщений для отправки
    - message_count: количество сообщений от каждого аккаунта (по умолчанию 100)
    - delay_min: минимальная задержка между сообщениями (по умолчанию 1)
    - delay_max: максимальная задержка между сообщениями (по умолчанию 5)

    Сообщения выбираются случайно из списка и повторяются циклично,
    пока не будет отправлено указанное количество сообщений.

    ВСЕ АККАУНТЫ РАБОТАЮТ ПАРАЛЛЕЛЬНО!
    """
    messages = config.get('messages', [])
    if not messages:
        return [{'error': 'Нет сообщений для отправки'}]

    # Запускаем все аккаунты параллельно
    tasks = [
        _send_messages_for_account(account_manager, account_id, config, stop_flag)
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
