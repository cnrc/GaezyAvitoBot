import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN
from app.utils.logging_config import setup_logging
from app.bot.handlers import base, search, admin, payments, tracking
from app.db import init_models
from app.middlewares import SubscriptionCheckMiddleware
from app.services.tracking_service import init_tracking_service
from aiogram.client.default import DefaultBotProperties

logger = setup_logging()

async def main():
    # Инициализация базы данных
    await init_models()
    logger.info("Database initialized")
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    dp = Dispatcher()

    # Регистрируем middleware для проверки подписки
    subscription_middleware = SubscriptionCheckMiddleware()
    dp.message.middleware(subscription_middleware)
    dp.callback_query.middleware(subscription_middleware)

    # Порядок регистрации роутеров важен!
    # Сначала регистрируем специализированные роутеры с конкретными фильтрами
    
    # 1. Роутеры с командами (обрабатываются по команде)
    dp.include_router(base.router)  # /start команда, help
    
    # 2. Роутеры с конкретными кнопками (регистрируем в порядке приоритета)
    dp.include_router(payments.router)    # "💳 Купить подписку" + callback queries
    
    dp.include_router(admin.router)  # /admin команда, промокоды, кнопки отмены
    
    dp.include_router(tracking.router)   # Отслеживание объявлений
    
    dp.include_router(search.router)     # "🔍 Найти объявления"

    # Устанавливаем команды бота (только /start и /help)
    commands = [
        BotCommand(command="start", description="🏠 Запустить бота"),
        BotCommand(command="help", description="❓ Помощь")
    ]
    await bot.set_my_commands(commands)

    # Инициализируем сервис отслеживания
    tracking_service = init_tracking_service(bot)
    
    # Запускаем сервис отслеживания в фоновой задаче
    tracking_task = asyncio.create_task(tracking_service.start_tracking())
    
    try:
        logger.info("Bot started")
        await dp.start_polling(bot)
    finally:
        # Останавливаем сервис отслеживания при завершении
        await tracking_service.stop_tracking()
        tracking_task.cancel()
        try:
            await tracking_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())
