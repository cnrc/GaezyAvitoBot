"""
Middleware для проверки подписки пользователя
"""
from typing import Callable, Dict, Any, Awaitable, Union
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from app.db import user_has_active_subscription, archive_all_user_trackings
from app.bot.handlers.base import get_main_keyboard


class SubscriptionCheckMiddleware(BaseMiddleware):
    """Middleware для автоматической проверки подписки"""
    
    def __init__(self):
        # Команды, которые должны работать всегда (независимо от подписки)
        self.allowed_commands = {
            '/start', '/help', '/admin', 
            '💳 Купить подписку', '🎟 Ввести промокод',
            '❌ Отменить ввод', '❌ Отменить', '❌ Отменить создание'
        }
        
        # Пользователи, у которых уже были заархивированы отслеживания в этой сессии
        self.archived_users = set()
    
    async def __call__(
        self,
        handler: Callable[[Union[Message, CallbackQuery], Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        """Проверяем подписку перед обработкой сообщения или callback"""
        
        # Для callback queries - блокируем только действия с отслеживаниями для пользователей без подписки
        if isinstance(event, CallbackQuery):
            telegram_id = str(event.from_user.id)
            
            # Блокируем только действия с отслеживаниями для пользователей без подписки
            if event.data and event.data.startswith(("archive_track:", "restore_track:", "delete_track:", "cancel_track_action")):
                has_subscription = await user_has_active_subscription(telegram_id)
                if not has_subscription:
                    print(f"🔒 MIDDLEWARE: Блокируем callback отслеживания от пользователя {telegram_id}: '{event.data}'")
                    await event.answer("⏰ Подписка истекла. Продлите подписку для продолжения.", show_alert=True)
                    return
            
            # Все остальные callback queries разрешаем (включая покупку подписки)
            print(f"✅ MIDDLEWARE: Разрешаем callback от пользователя {telegram_id}: '{event.data}'")
            return await handler(event, data)
        
        # Пропускаем системные сообщения
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)
        
        telegram_id = str(event.from_user.id)
        
        # Пропускаем разрешенные команды
        if event.text in self.allowed_commands or event.text.startswith(('/start', '/help', '/admin')):
            print(f"✅ MIDDLEWARE: Разрешаем команду от пользователя {telegram_id}: '{event.text}'")
            return await handler(event, data)
        
        # Импортируем состояния промокодов и отслеживаний - разрешаем их обработку
        try:
            from app.bot.handlers.admin import promo_state
            if int(telegram_id) in promo_state:
                print(f"🔓 MIDDLEWARE: Разрешаем ввод промокода для пользователя {telegram_id}: '{event.text}'")
                return await handler(event, data)
        except (ImportError, ValueError):
            pass
            
        # Разрешаем ввод названий отслеживаний только для пользователей с подпиской
        try:
            from app.bot.handlers.tracking import tracking_states
            user_id = event.from_user.id
            if user_id in tracking_states:
                has_subscription = await user_has_active_subscription(telegram_id)
                if has_subscription:
                    return await handler(event, data)
                else:
                    # Очищаем состояние если подписки нет
                    tracking_states.pop(user_id, None)
        except (ImportError, ValueError):
            pass
        
        # Проверяем активную подписку
        has_subscription = await user_has_active_subscription(telegram_id)
        
        if not has_subscription:
            print(f"🔒 MIDDLEWARE: Блокируем сообщение от пользователя {telegram_id}: '{event.text}'")
            print(f"🔒 Пользователь {telegram_id} без подписки пытается использовать бота")
            
            # Архивируем отслеживания только один раз за сессию
            archived_count = 0
            if telegram_id not in self.archived_users:
                archived_count = await archive_all_user_trackings(telegram_id)
                self.archived_users.add(telegram_id)
                
                if archived_count > 0:
                    print(f"🗂️ Заархивировано {archived_count} отслеживаний для пользователя {telegram_id}")
            
            # Формируем сообщение
            if archived_count > 0:
                message = (
                    "⏰ <b>Подписка истекла</b>\n\n"
                    f"🗂️ Ваши отслеживания ({archived_count} шт.) были автоматически заархивированы.\n\n"
                    "💡 Продлите подписку, чтобы восстановить отслеживания и продолжить пользоваться ботом."
                )
            else:
                message = (
                    "⏰ <b>Подписка истекла</b>\n\n" 
                    "💡 Продлите подписку, чтобы продолжить пользоваться ботом."
                )
            
            # Показываем клавиатуру для покупки подписки
            keyboard = await get_main_keyboard(telegram_id)
            
            await event.answer(message, reply_markup=keyboard, parse_mode="HTML")
            
            # Прекращаем обработку сообщения
            return
        
        # Если подписка активна, убираем пользователя из списка заархивированных
        if telegram_id in self.archived_users:
            self.archived_users.remove(telegram_id)
        
        # Продолжаем нормальную обработку
        print(f"✅ MIDDLEWARE: Разрешаем сообщение от пользователя {telegram_id}: '{event.text}'")
        return await handler(event, data)
