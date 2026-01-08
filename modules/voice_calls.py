import asyncio
import os
import random
import logging
from typing import List, Dict, Optional
from telethon.errors import FloodWaitError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from modules.account_manager import AccountManager
import config

logger = logging.getLogger(__name__)

# Попытка импорта pytgcalls с обработкой разных версий
PYTGCALLS_AVAILABLE = False
PYTGCALLS_ERROR = None
PYTGCALLS_VERSION = None

try:
    import pytgcalls
    # Определяем версию по атрибуту __version__
    version = getattr(pytgcalls, '__version__', '0.0.0')
    logger.info(f"Обнаружена pytgcalls версия: {version}")

    # Для версий 2.x и выше используем PyTgCalls с MediaStream API
    from pytgcalls import PyTgCalls
    PYTGCALLS_AVAILABLE = True
    PYTGCALLS_VERSION = "2.x+"
    logger.info(f"Используется API PyTgCalls для версии {version}")

except ImportError as e:
    PYTGCALLS_ERROR = str(e)
    PYTGCALLS_AVAILABLE = False
    PYTGCALLS_VERSION = None


async def join_voice_chat(
    account_manager: AccountManager,
    account_ids: List[int],
    task_config: Dict,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Массовый заход в голосовой чат и воспроизведение аудио

    config:
    - group_link: ссылка на группу/чат
    - audio_file: путь к аудиофайлу или имя файла из audio/
    - playback_mode: режим воспроизведения (sync/relay/random)
    - duration: длительность в секундах (0 = до конца файла)
    - enable_video: включить видео (True/False)
    - video_file: путь к видеофайлу (если enable_video=True)
    """
    # Проверка доступности pytgcalls
    if not PYTGCALLS_AVAILABLE:
        error_msg = f'Библиотека pytgcalls недоступна. Установите: pip install pytgcalls. Ошибка: {PYTGCALLS_ERROR}'
        return [{'account_id': aid, 'success': False, 'error': error_msg} for aid in account_ids]

    group_link = task_config.get('group_link')
    audio_file = task_config.get('audio_file')
    playback_mode = task_config.get('playback_mode', 'sync')
    duration = task_config.get('duration', 0)
    enable_video = task_config.get('enable_video', False)
    video_file = task_config.get('video_file')

    # Определяем пути к файлам
    audio_path = _resolve_media_path(audio_file, config.AUDIO_DIR) if audio_file else None
    video_path = _resolve_media_path(video_file, config.VIDEO_DIR) if enable_video and video_file else None

    # Валидация файлов
    if audio_path and not os.path.exists(audio_path):
        return [{'account_id': aid, 'success': False, 'error': f'Аудиофайл не найден: {audio_path}'} for aid in account_ids]

    if enable_video and video_path and not os.path.exists(video_path):
        return [{'account_id': aid, 'success': False, 'error': f'Видеофайл не найден: {video_path}'} for aid in account_ids]

    # Выбор режима воспроизведения
    if playback_mode == 'sync':
        return await _play_sync(account_manager, account_ids, group_link, audio_path, video_path, duration, enable_video, stop_flag)
    elif playback_mode == 'relay':
        return await _play_relay(account_manager, account_ids, group_link, audio_path, video_path, duration, enable_video, stop_flag)
    elif playback_mode == 'random':
        return await _play_random(account_manager, account_ids, group_link, duration, enable_video, stop_flag)
    else:
        return [{'account_id': aid, 'success': False, 'error': f'Неизвестный режим: {playback_mode}'} for aid in account_ids]


async def _play_sync(
    account_manager: AccountManager,
    account_ids: List[int],
    group_link: str,
    audio_path: Optional[str],
    video_path: Optional[str],
    duration: int,
    enable_video: bool,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Синхронное воспроизведение - все аккаунты играют один файл одновременно
    """
    tasks = [
        _play_media_for_account(
            account_manager,
            account_id,
            group_link,
            audio_path,
            video_path,
            duration,
            enable_video,
            stop_flag
        )
        for account_id in account_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обработка результатов
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                'account_id': account_ids[i],
                'success': False,
                'error': str(result)
            })
        else:
            processed_results.append(result)

    return processed_results


async def _play_relay(
    account_manager: AccountManager,
    account_ids: List[int],
    group_link: str,
    audio_path: Optional[str],
    video_path: Optional[str],
    duration: int,
    enable_video: bool,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Relay режим - аккаунты играют по очереди, дожидаясь завершения предыдущего
    """
    results = []

    for account_id in account_ids:
        if stop_flag.is_set():
            results.append({
                'account_id': account_id,
                'success': False,
                'error': 'Остановлено пользователем'
            })
            continue

        result = await _play_media_for_account(
            account_manager,
            account_id,
            group_link,
            audio_path,
            video_path,
            duration,
            enable_video,
            stop_flag
        )
        results.append(result)

        # Задержка между аккаунтами
        if not stop_flag.is_set():
            await asyncio.sleep(random.uniform(2, 5))

    return results


async def _play_random(
    account_manager: AccountManager,
    account_ids: List[int],
    group_link: str,
    duration: int,
    enable_video: bool,
    stop_flag: asyncio.Event
) -> List[Dict]:
    """
    Random режим - каждый аккаунт играет случайный файл из папки
    """
    # Получаем список файлов
    audio_files = [f for f in os.listdir(config.AUDIO_DIR) if f.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))]
    video_files = [f for f in os.listdir(config.VIDEO_DIR) if f.endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm'))] if enable_video else []

    if not audio_files:
        return [{'account_id': aid, 'success': False, 'error': 'Нет аудиофайлов в папке audio/'} for aid in account_ids]

    if enable_video and not video_files:
        return [{'account_id': aid, 'success': False, 'error': 'Нет видеофайлов в папке video/'} for aid in account_ids]

    tasks = []
    for account_id in account_ids:
        random_audio = os.path.join(config.AUDIO_DIR, random.choice(audio_files))
        random_video = os.path.join(config.VIDEO_DIR, random.choice(video_files)) if enable_video else None

        task = _play_media_for_account(
            account_manager,
            account_id,
            group_link,
            random_audio,
            random_video,
            duration,
            enable_video,
            stop_flag
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Обработка результатов
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                'account_id': account_ids[i],
                'success': False,
                'error': str(result)
            })
        else:
            processed_results.append(result)

    return processed_results


async def _join_group_if_needed(client, group_link: str):
    """
    Присоединяется к группе, если клиент еще не в ней
    """
    # Очищаем ссылку от параметров (?videochat и т.д.)
    clean_link = group_link.split('?')[0]

    try:
        # Пробуем получить entity
        entity = await client.get_entity(clean_link)

        # Проверяем, состоит ли клиент в группе
        try:
            participant = await client.get_permissions(entity)
            logger.info(f"Клиент уже в группе {entity.id}")
            return entity
        except:
            # Не в группе, нужно присоединиться
            pass

        # Присоединяемся к группе
        if '/joinchat/' in clean_link or '/+' in clean_link:
            # Пригласительная ссылка
            invite_hash = clean_link.split('/')[-1].replace('+', '')
            logger.info(f"Присоединение по пригласительной ссылке: {invite_hash}")
            await client(ImportChatInviteRequest(invite_hash))
        else:
            # Публичная группа
            logger.info(f"Присоединение к публичной группе: {entity.username}")
            await client(JoinChannelRequest(entity))

        logger.info(f"Успешно присоединились к группе {entity.id}")
        return entity

    except UserAlreadyParticipantError:
        logger.info(f"Клиент уже в группе")
        entity = await client.get_entity(clean_link)
        return entity
    except Exception as e:
        logger.error(f"Ошибка присоединения к группе: {str(e)}")
        raise


async def _play_media_for_account(
    account_manager: AccountManager,
    account_id: int,
    group_link: str,
    audio_path: Optional[str],
    video_path: Optional[str],
    duration: int,
    enable_video: bool,
    stop_flag: asyncio.Event
) -> Dict:
    """
    Воспроизведение медиа для одного аккаунта
    """
    result = {
        'account_id': account_id,
        'success': False,
        'error': None,
        'media_played': None
    }

    group_call = None
    chat_id = None

    try:
        logger.info(f"[Account {account_id}] Начало подключения к голосовому чату")

        # Получаем Telethon клиент
        client = await account_manager.get_client(account_id)
        if not client:
            result['error'] = 'Не удалось подключиться к аккаунту'
            logger.error(f"[Account {account_id}] {result['error']}")
            return result

        # Присоединяемся к группе, если нужно, и получаем entity
        try:
            entity = await _join_group_if_needed(client, group_link)
            chat_id = entity.id
            logger.info(f"[Account {account_id}] Группа найдена: {chat_id}")
        except Exception as e:
            result['error'] = f'Не удалось присоединиться к группе: {str(e)}'
            logger.error(f"[Account {account_id}] {result['error']}")
            return result

        # Создаем PyTgCalls клиент для присоединения к голосовому чату
        try:
            logger.info(f"[Account {account_id}] Инициализация pytgcalls клиента")

            from pytgcalls import PyTgCalls

            # Получаем ID текущего пользователя для установки default_join_as
            me = await client.get_me()
            logger.info(f"[Account {account_id}] Присоединение от имени пользователя {me.id}")

            # Создаем PyTgCalls клиент с указанием default_join_as
            # Передаем peer_id пользователя, чтобы присоединяться от его имени, а не от имени канала
            group_call = PyTgCalls(client, default_join_as=me.id)
            await group_call.start()

            logger.info(f"[Account {account_id}] PyTgCalls клиент запущен с default_join_as={me.id}")

        except Exception as e:
            result['error'] = f'Ошибка инициализации pytgcalls: {str(e)}'
            logger.error(f"[Account {account_id}] {result['error']}")
            return result

        # Присоединяемся к СУЩЕСТВУЮЩЕМУ голосовому чату и воспроизводим медиа
        try:
            logger.info(f"[Account {account_id}] Присоединение к существующему голосовому чату и воспроизведение")

            # Используем MediaStream API
            from pytgcalls.types import MediaStream

            if enable_video and audio_path and video_path:
                # Аудио + Видео
                logger.info(f"[Account {account_id}] Воспроизведение аудио+видео: {os.path.basename(audio_path)}, {os.path.basename(video_path)}")
                await group_call.play(
                    chat_id,
                    MediaStream(
                        audio_path,
                        video_path
                    )
                )
                result['media_played'] = f'audio: {os.path.basename(audio_path)}, video: {os.path.basename(video_path)}'
            elif audio_path:
                # Только аудио
                logger.info(f"[Account {account_id}] Воспроизведение аудио: {os.path.basename(audio_path)}")
                await group_call.play(
                    chat_id,
                    MediaStream(
                        audio_path,
                        video_flags=MediaStream.Flags.IGNORE
                    )
                )
                result['media_played'] = f'audio: {os.path.basename(audio_path)}'
            else:
                result['error'] = 'Не указан медиафайл'
                logger.error(f"[Account {account_id}] {result['error']}")
                return result

            result['success'] = True
            result['action'] = 'joined_and_playing'
            logger.info(f"[Account {account_id}] Воспроизведение началось успешно")

        except Exception as e:
            result['error'] = f'Не удалось присоединиться/воспроизвести: {str(e)}'
            logger.error(f"[Account {account_id}] {result['error']}", exc_info=True)
            try:
                await group_call.leave_group_call(chat_id)
            except:
                pass
            return result

        # Ожидание завершения
        if duration > 0:
            # Фиксированная длительность
            logger.info(f"[Account {account_id}] Воспроизведение на {duration} секунд")
            wait_time = 0
            while wait_time < duration and not stop_flag.is_set():
                await asyncio.sleep(1)
                wait_time += 1
        else:
            # До конца файла или до stop_flag
            logger.info(f"[Account {account_id}] Воспроизведение до остановки")
            while not stop_flag.is_set():
                await asyncio.sleep(1)

        # Выходим из голосового чата
        logger.info(f"[Account {account_id}] Выход из голосового чата")
        try:
            await group_call.leave_group_call(chat_id)
            logger.info(f"[Account {account_id}] Успешно вышли из голосового чата")
        except Exception as e:
            result['error'] = f'Ошибка выхода: {str(e)}'
            logger.error(f"[Account {account_id}] {result['error']}")

    except FloodWaitError as e:
        result['error'] = f'Флуд-контроль: {e.seconds} сек'
        logger.error(f"[Account {account_id}] {result['error']}")

    except Exception as e:
        result['error'] = f'Неожиданная ошибка: {str(e)}'
        logger.error(f"[Account {account_id}] {result['error']}", exc_info=True)

    finally:
        # Очистка ресурсов
        if group_call and chat_id:
            try:
                await group_call.leave_group_call(chat_id)
            except:
                pass

    logger.info(f"[Account {account_id}] Завершение работы. Success={result['success']}")
    return result


def _resolve_media_path(filename: str, media_dir: str) -> str:
    """
    Определяет полный путь к медиафайлу
    """
    # Если это уже полный путь
    if os.path.isabs(filename):
        return filename

    # Если это просто имя файла
    return os.path.join(media_dir, filename)


def get_available_audio_files() -> List[str]:
    """
    Возвращает список доступных аудиофайлов
    """
    try:
        files = [
            f for f in os.listdir(config.AUDIO_DIR)
            if f.endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))
        ]
        return sorted(files)
    except Exception:
        return []


def get_available_video_files() -> List[str]:
    """
    Возвращает список доступных видеофайлов
    """
    try:
        files = [
            f for f in os.listdir(config.VIDEO_DIR)
            if f.endswith(('.mp4', '.avi', '.mkv', '.mov', '.webm'))
        ]
        return sorted(files)
    except Exception:
        return []
