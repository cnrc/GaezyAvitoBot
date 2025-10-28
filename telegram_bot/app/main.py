import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN, CHECK_INTERVAL
from app.utils.logging_config import setup_logging
from app.bot.handlers import base, search, admin, payments
from app.bot import scheduler
from app.db import init_models
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


    # Порядок регистрации роутеров важен!
    # Сначала регистрируем специализированные роутеры с конкретными фильтрами
    
    # 1. Роутеры с командами (обрабатываются по команде)
    dp.include_router(base.router)  # /start команда, help
    
    # 2. Роутеры с конкретными кнопками (регистрируем в порядке приоритета)
    dp.include_router(payments.router)    # "💳 Купить подписку" + callback queries
    
    dp.include_router(admin.router)  # /admin команда, промокоды, кнопки отмены
    
    dp.include_router(search.router)     # "🔍 Найти объявления"

    # Запуск фоновой задачи проверки цен
    async def loop_check():
        while True:
            try:
                await scheduler.check_prices(bot)
            except Exception:
                pass
            await asyncio.sleep(CHECK_INTERVAL)

    asyncio.create_task(loop_check())

    logger.info("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
