import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN, CHECK_INTERVAL
from app.utils.logging_config import setup_logging
from app.bot.handlers import base, tracking, search, admin, payments
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
    
    print("🔍 MAIN: Начинаем регистрацию роутеров")
    
    # 1. Роутеры с командами (обрабатываются по команде)
    print("🔍 MAIN: Регистрируем base.router")
    dp.include_router(base.router)  # /start команда, help
    print("🔍 MAIN: base.router зарегистрирован")
    
    # 2. Роутеры с конкретными кнопками (регистрируем в порядке приоритета)
    print("🔍 MAIN: Регистрируем payments.router")
    dp.include_router(payments.router)    # "💳 Купить подписку" + callback queries
    print("🔍 MAIN: payments.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем admin.router")
    dp.include_router(admin.router)  # /admin команда, промокоды, кнопки отмены
    print("🔍 MAIN: admin.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем search.router")
    dp.include_router(search.router)     # "🔍 Найти объявления"
    print("🔍 MAIN: search.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем tracking.router")
    dp.include_router(tracking.router)   # "📋 Мои отслеживаемые", "🗑️ Удалить объявление", добавление объявлений
    print("🔍 MAIN: tracking.router зарегистрирован")
    
    print("🔍 MAIN: Все роутеры зарегистрированы успешно")

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
