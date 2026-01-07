from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database import Database
import config


class AdminCheckMiddleware(BaseMiddleware):
    """Middleware для проверки прав админа"""

    def __init__(self, db: Database):
        self.db = db
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id из события
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if not user_id:
            return await handler(event, data)

        # Проверяем, является ли пользователь админом из config
        if user_id == config.ADMIN_ID:
            # Убеждаемся, что супер-админ есть в базе
            admin = await self.db.get_admin(user_id)
            if not admin:
                await self.db.add_admin(
                    user_id=user_id,
                    is_super_admin=True
                )
            data['is_admin'] = True
            data['is_super_admin'] = True
            return await handler(event, data)

        # Проверяем, есть ли пользователь в таблице админов
        is_admin = await self.db.is_admin(user_id)
        if not is_admin:
            # Не админ - отказываем в доступе
            if isinstance(event, Message):
                await event.answer("❌ У вас нет доступа к этому боту.")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ У вас нет доступа к этому боту.", show_alert=True)
            return

        # Пользователь - админ, проверяем супер-админа
        is_super = await self.db.is_super_admin(user_id)
        data['is_admin'] = True
        data['is_super_admin'] = is_super

        return await handler(event, data)
