import asyncio
import random
import re
from typing import List, Dict, Optional, Tuple
from telethon.tl import functions, types
from telethon.errors import FloodWaitError, ChannelPrivateError, InviteHashExpiredError
from modules.account_manager import AccountManager


def parse_post_link(post_link: str) -> Optional[Tuple[str, int]]:
    """
    Парсит ссылку на пост и возвращает (channel, message_id)

    Поддерживаемые форматы:
    - https://t.me/channel/123
    - https://t.me/c/1234567890/123
    - t.me/channel/123
    """
    # Паттерн для публичных каналов: t.me/channel/message_id
    public_pattern = r'(?:https?://)?t\.me/([^/]+)/(\d+)'
    # Паттерн для приватных каналов: t.me/c/channel_id/message_id
    private_pattern = r'(?:https?://)?t\.me/c/(\d+)/(\d+)'

    public_match = re.match(public_pattern, post_link)
    if public_match:
        channel = public_match.group(1)
        message_id = int(public_match.group(2))
        return (channel, message_id)

    private_match = re.match(private_pattern, post_link)
    if private_match:
        channel_id = int(private_match.group(1))
        message_id = int(private_match.group(2))
        # Для приватных каналов возвращаем ID канала с префиксом -100
        return (f"-100{channel_id}", message_id)

    return None


async def _set_reactions_for_account(
    account_manager: AccountManager,
    account_id: int,
    config: Dict,
    stop_flag: asyncio.Event,
    reactions_list: List[str]
) -> Dict:
    """Установка реакций для одного аккаунта"""
    post_link = config.get('post_link')
    group_link = config.get('group_link')
    invite_link = config.get('invite_link')
    message_id = config.get('message_id')
    posts_count = config.get('posts_count', 10)
    reaction = config.get('reaction', '👍')
    random_reactions = config.get('random_reactions', False)
    delay_min = config.get('delay_min', 0)
    delay_max = config.get('delay_max', 1)

    # Если указана ссылка на пост, парсим её
    if post_link:
        parsed = parse_post_link(post_link)
        if parsed:
            parsed_channel, parsed_message_id = parsed
            group_link = parsed_channel
            message_id = parsed_message_id
        else:
            return {'account_id': account_id, 'reactions_set': 0, 'success': False, 'error': f'Неверный формат ссылки на пост: {post_link}'}

    if not group_link:
        return {'account_id': account_id, 'reactions_set': 0, 'success': False, 'error': 'Не указана ссылка на канал или пост'}

    result = {
        'account_id': account_id,
        'reactions_set': 0,
        'success': False,
        'error': None
    }

    try:
        client = await account_manager.get_client(account_id)
        if not client:
            result['error'] = 'Не удалось подключиться к аккаунту'
            return result

        # Если указана ссылка-приглашение для приватного канала, присоединяемся
        if invite_link:
            try:
                # Извлекаем хеш из ссылки-приглашения
                invite_hash = invite_link.split('/')[-1].replace('+', '')
                # Присоединяемся к приватному каналу
                await client(functions.messages.ImportChatInviteRequest(hash=invite_hash))
                # Небольшая задержка после присоединения
                await asyncio.sleep(1)
            except InviteHashExpiredError:
                result['error'] = 'Ссылка-приглашение истекла'
                return result
            except Exception as e:
                # Если уже в канале, игнорируем ошибку
                if 'already' not in str(e).lower():
                    result['error'] = f'Ошибка присоединения к каналу: {str(e)}'
                    return result

        # Получаем entity
        try:
            entity = await client.get_entity(group_link)
        except ChannelPrivateError:
            result['error'] = 'Приватный канал недоступен. Укажите ссылку-приглашение'
            return result
        except Exception as e:
            result['error'] = f'Чат не найден: {str(e)}'
            return result

        # Если указан конкретный message_id, ставим реакцию только на него
        if message_id:
            selected_reaction = random.choice(reactions_list) if random_reactions else reaction

            try:
                await client(functions.messages.SendReactionRequest(
                    peer=entity,
                    msg_id=message_id,
                    reaction=[types.ReactionEmoji(emoticon=selected_reaction)]
                ))

                result['reactions_set'] = 1
                result['success'] = True
                result['reaction'] = selected_reaction

            except Exception as e:
                result['error'] = f'Ошибка установки реакции: {str(e)}'

        # Иначе ставим реакции на последние посты
        else:
            try:
                # Получаем последние сообщения из канала/группы
                messages = await client.get_messages(entity, limit=posts_count)

                for msg in messages:
                    if stop_flag.is_set():
                        break

                    # Пропускаем служебные сообщения
                    if not msg.text and not msg.media:
                        continue

                    selected_reaction = random.choice(reactions_list) if random_reactions else reaction

                    try:
                        await client(functions.messages.SendReactionRequest(
                            peer=entity,
                            msg_id=msg.id,
                            reaction=[types.ReactionEmoji(emoticon=selected_reaction)]
                        ))

                        result['reactions_set'] += 1

                        # Задержка между реакциями
                        if delay_max > 0:
                            await asyncio.sleep(random.uniform(delay_min, delay_max))

                    except FloodWaitError as e:
                        result['error'] = f'Флуд-контроль: {e.seconds} сек'
                        break
                    except Exception as e:
                        # Игнорируем отдельные ошибки, продолжаем ставить реакции
                        pass

                result['success'] = result['reactions_set'] > 0

            except Exception as e:
                result['error'] = f'Ошибка получения сообщений: {str(e)}'

    except FloodWaitError as e:
        result['error'] = f'Флуд-контроль: {e.seconds} сек'

    except Exception as e:
        result['error'] = str(e)

    return result


async def set_reactions(
    account_manager: AccountManager,
    account_ids: List[int],
    config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Установка реакций на сообщение (ПАРАЛЛЕЛЬНО)

    config:
    - post_link: прямая ссылка на пост (например, https://t.me/channel/123)
    - group_link: ссылка на группу/канал (если post_link не указан)
    - invite_link: ссылка-приглашение для приватного канала (опционально)
    - message_id: ID сообщения (опционально, если не указан - ставит на последние посты)
    - posts_count: количество последних постов для реакций (по умолчанию 10)
    - reaction: эмодзи реакции (например, '👍', '❤️', '🔥')
    - random_reactions: использовать случайные реакции (True/False)
    - delay_min: минимальная задержка между реакциями (по умолчанию 0)
    - delay_max: максимальная задержка между реакциями (по умолчанию 1)

    ВСЕ АККАУНТЫ РАБОТАЮТ ПАРАЛЛЕЛЬНО!
    """
    # Полный список всех доступных реакций в Telegram
    reactions_list = [
        '👍', '👎', '❤️', '🔥', '🥰', '👏', '😁', '🤔', '🤯', '😱',
        '🤬', '😢', '🎉', '🤩', '🤮', '💩', '🙏', '👌', '🕊', '🤡',
        '🥱', '🥴', '😍', '🐳', '❤️‍🔥', '🌚', '🌭', '💯', '🤣', '⚡',
        '🍌', '🏆', '💔', '🤨', '😐', '🍓', '🍾', '💋', '🖕', '😈',
        '😴', '😭', '🤓', '👻', '👨‍💻', '👀', '🎃', '🙈', '😇', '😨',
        '🤝', '✍️', '🤗', '🫡', '🎅', '🎄', '☃️', '💅', '🤪', '🗿',
        '🆒', '💘', '🙉', '🦄', '😘', '💊', '🙊', '😎', '👾', '🤷‍♂️',
        '🤷', '🤷‍♀️', '😡'
    ]

    # Запускаем все аккаунты параллельно
    tasks = [
        _set_reactions_for_account(account_manager, account_id, config, stop_flag, reactions_list)
        for account_id in account_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обрабатываем исключения
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append({
                'account_id': account_ids[i],
                'reactions_set': 0,
                'success': False,
                'error': str(result)
            })
        else:
            final_results.append(result)

    return final_results
