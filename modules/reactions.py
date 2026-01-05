import asyncio
import random
from typing import List, Dict
from telethon.tl import functions, types
from telethon.errors import FloodWaitError
from modules.account_manager import AccountManager

async def set_reactions(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Установка реакций на сообщение

    config:
    - group_link: ссылка на группу/канал
    - message_id: ID сообщения
    - reaction: эмодзи реакции (например, '👍', '❤️', '🔥')
    - random_reactions: использовать случайные реакции (True/False)
    """
    results = []
    group_link = config.get('group_link')
    message_id = config.get('message_id')
    reaction = config.get('reaction', '👍')
    random_reactions = config.get('random_reactions', False)

    # Список популярных реакций
    reactions_list = ['👍', '❤️', '🔥', '🥰', '😁', '😮', '😢', '🤔', '👏', '🎉']

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

            # Получаем entity
            try:
                entity = await client.get_entity(group_link)
            except Exception as e:
                result['error'] = f'Чат не найден: {str(e)}'
                results.append(result)
                continue

            # Выбираем реакцию
            selected_reaction = random.choice(reactions_list) if random_reactions else reaction

            try:
                # Отправляем реакцию
                await client(functions.messages.SendReactionRequest(
                    peer=entity,
                    msg_id=message_id,
                    reaction=[types.ReactionEmoji(emoticon=selected_reaction)]
                ))

                result['success'] = True
                result['reaction'] = selected_reaction

            except Exception as e:
                result['error'] = f'Ошибка установки реакции: {str(e)}'

        except FloodWaitError as e:
            result['error'] = f'Флуд-контроль: {e.seconds} сек'

        except Exception as e:
            result['error'] = str(e)

        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(1, 3))

    return results
