import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN
from app.utils.logging_config import setup_logging
from app.bot.handlers import base, search, admin, payments, tracking
from app.bot import scheduler
from app.db import init_models
from app.middlewares import SubscriptionCheckMiddleware
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

    # Запуск фоновой задачи проверки цен (каждые 5 минут)
    async def loop_check():
        while True:
            try:
                await scheduler.check_prices(bot)
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
            await asyncio.sleep(300)  # 300 секунд = 5 минут

    asyncio.create_task(loop_check())

    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
