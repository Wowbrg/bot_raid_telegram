import asyncio
import json
from typing import Dict, List, Optional
from database import Database
from modules.account_manager import AccountManager
import random

class TaskManager:
    """Управление задачами юзерботов"""

    def __init__(self, db: Database, account_manager: AccountManager):
        self.db = db
        self.account_manager = account_manager
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.stop_flags: Dict[int, asyncio.Event] = {}

    async def create_task(
        self,
        task_type: str,
        config: Dict,
        account_ids: List[int]
    ) -> int:
        """Создать и запустить задачу"""
        # Сохраняем в БД
        task_id = await self.db.create_task(
            task_type=task_type,
            config=json.dumps(config),
            accounts_used=json.dumps(account_ids)
        )

        # Создаем флаг остановки
        stop_flag = asyncio.Event()
        self.stop_flags[task_id] = stop_flag

        # Запускаем задачу в фоне
        task = asyncio.create_task(
            self._run_task(task_id, task_type, config, account_ids, stop_flag)
        )
        self.active_tasks[task_id] = task

        return task_id

    async def _run_task(
        self,
        task_id: int,
        task_type: str,
        config: Dict,
        account_ids: List[int],
        stop_flag: asyncio.Event
    ):
        """Выполнить задачу"""
        await self.db.update_task_status(task_id, 'running')
        results = []

        try:
            # Применяем пользовательские настройки скорости, если они есть
            speed_settings = await self.db.get_speed_settings(task_type)
            if speed_settings:
                # Обновляем config с пользовательскими настройками скорости
                config['delay_min'] = speed_settings.get('delay_min', config.get('delay_min', 1.0))
                config['delay_max'] = speed_settings.get('delay_max', config.get('delay_max', 3.0))
                config['account_delay_min'] = speed_settings.get('account_delay_min', config.get('account_delay_min', 2.0))
                config['account_delay_max'] = speed_settings.get('account_delay_max', config.get('account_delay_max', 5.0))

                # Для массовой рассылки также обновляем message_delay
                if task_type == 'mass_messaging':
                    config['delay_min'] = speed_settings.get('message_delay_min', config.get('delay_min', 1.0))
                    config['delay_max'] = speed_settings.get('message_delay_max', config.get('delay_max', 5.0))

            # Импортируем нужный модуль в зависимости от типа задачи
            if task_type == 'join_leave_groups':
                from modules.group_actions import join_leave_groups
                results = await join_leave_groups(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'screenshot_spam':
                from modules.screenshot_spam import send_screenshot_notifications
                results = await send_screenshot_notifications(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'mass_messaging':
                from modules.mass_messaging import send_mass_messages
                results = await send_mass_messages(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'voice_call':
                from modules.voice_calls import join_voice_call
                results = await join_voice_call(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'set_reactions':
                from modules.reactions import set_reactions
                results = await set_reactions(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'subscribe_channel':
                from modules.subscriptions import subscribe_to_channels
                results = await subscribe_to_channels(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'start_bots' or task_type == 'start_bot':
                from modules.bot_starter import start_bots
                results = await start_bots(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            elif task_type == 'cleanup_account':
                from modules.cleanup import cleanup_accounts
                results = await cleanup_accounts(
                    self.account_manager,
                    account_ids,
                    config,
                    stop_flag
                )

            # Задача завершена
            await self.db.update_task_status(
                task_id,
                'completed',
                json.dumps(results)
            )

        except asyncio.CancelledError:
            # Задача остановлена
            await self.db.update_task_status(
                task_id,
                'stopped',
                json.dumps(results)
            )

        except Exception as e:
            # Ошибка выполнения
            await self.db.update_task_status(
                task_id,
                'failed',
                json.dumps({'error': str(e)})
            )

        finally:
            # Очистка
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
            if task_id in self.stop_flags:
                del self.stop_flags[task_id]

    async def stop_task(self, task_id: int) -> bool:
        """Остановить задачу"""
        if task_id in self.stop_flags:
            self.stop_flags[task_id].set()

        if task_id in self.active_tasks:
            self.active_tasks[task_id].cancel()
            try:
                await self.active_tasks[task_id]
            except asyncio.CancelledError:
                pass
            return True

        return False

    async def stop_all_tasks(self):
        """Остановить все задачи"""
        task_ids = list(self.active_tasks.keys())
        for task_id in task_ids:
            await self.stop_task(task_id)

    def get_active_task_ids(self) -> List[int]:
        """Получить ID активных задач"""
        return list(self.active_tasks.keys())
