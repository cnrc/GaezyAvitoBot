import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN, CHECK_INTERVAL
from app.utils.logging_config import setup_logging
from app.bot.handlers import start, help, list_items, remove, messages, search, admin, payments
from app.bot import scheduler
from app.db.model import init_models
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


    dp.include_router(payments.router)
    
    dp.include_router(start.router)
    dp.include_router(admin.router) 
    
    # Сначала все специализированные роутеры, затем общий messages
    dp.include_router(help.router)
    dp.include_router(list_items.router)
    dp.include_router(remove.router)
    dp.include_router(search.router)
    
    # messages.router регистрируем последним
    dp.include_router(messages.router)
    

    # Устанавливаем команды бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Запуск бота"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="search", description="Поиск объявлений"),
        BotCommand(command="list", description="Список отслеживаемых"),
        BotCommand(command="remove", description="Удалить объявление"),
        BotCommand(command="admin", description="Админ-панель")
    ])

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
