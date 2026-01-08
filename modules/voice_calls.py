import asyncio
import os
import random
from typing import List, Dict, Optional
from telethon.errors import FloodWaitError
from pytgcalls import GroupCallFactory
from modules.account_manager import AccountManager
import config


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

    try:
        # Получаем Telethon клиент
        client = await account_manager.get_client(account_id)
        if not client:
            result['error'] = 'Не удалось подключиться к аккаунту'
            return result

        # Получаем entity группы
        try:
            entity = await client.get_entity(group_link)
            chat_id = entity.id
        except Exception as e:
            result['error'] = f'Группа не найдена: {str(e)}'
            return result

        # Создаем GroupCall через фабрику
        group_call = GroupCallFactory(client).get_file_group_call()

        # Присоединяемся к голосовому чату
        try:
            await group_call.start(chat_id)
        except Exception as e:
            result['error'] = f'Не удалось присоединиться к голосовому чату: {str(e)}'
            return result

        # Воспроизводим медиа
        try:
            if enable_video and audio_path and video_path:
                # Аудио + Видео
                await group_call.play_file(
                    audio_path,
                    video_path=video_path,
                    repeat=False
                )
                result['media_played'] = f'audio: {os.path.basename(audio_path)}, video: {os.path.basename(video_path)}'
            elif audio_path:
                # Только аудио
                await group_call.play_file(audio_path, repeat=False)
                result['media_played'] = f'audio: {os.path.basename(audio_path)}'
            else:
                result['error'] = 'Не указан медиафайл'
                await group_call.stop()
                return result

            result['success'] = True
            result['action'] = 'joined_and_playing'
        except Exception as e:
            result['error'] = f'Ошибка воспроизведения: {str(e)}'
            await group_call.stop()
            return result

        # Ожидание завершения
        if duration > 0:
            # Фиксированная длительность
            wait_time = 0
            while wait_time < duration and not stop_flag.is_set():
                await asyncio.sleep(1)
                wait_time += 1
        else:
            # До конца файла или до stop_flag
            while not stop_flag.is_set():
                # Проверяем, играет ли еще файл
                if not group_call.is_connected:
                    break
                await asyncio.sleep(1)

        # Выходим из голосового чата
        try:
            await group_call.stop()
        except Exception as e:
            result['error'] = f'Ошибка выхода: {str(e)}'

    except FloodWaitError as e:
        result['error'] = f'Флуд-контроль: {e.seconds} сек'

    except Exception as e:
        result['error'] = f'Неожиданная ошибка: {str(e)}'

    finally:
        # Очистка ресурсов
        if group_call:
            try:
                await group_call.stop()
            except:
                pass

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
