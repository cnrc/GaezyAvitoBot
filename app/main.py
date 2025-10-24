import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN, CHECK_INTERVAL
from app.utils.logging_config import setup_logging
from app.bot.handlers import start, help, list_items, remove, messages, search, admin, payments, promocodes
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


    # Порядок регистрации роутеров важен!
    # Сначала регистрируем специализированные роутеры с конкретными фильтрами
    
    print("🔍 MAIN: Начинаем регистрацию роутеров")
    
    # 1. Роутеры с командами (обрабатываются по команде)
    print("🔍 MAIN: Регистрируем start.router")
    dp.include_router(start.router)  # /start команда
    print("🔍 MAIN: Регистрируем admin.router")
    dp.include_router(admin.router)  # /admin команда
    
    # 2. Роутеры с конкретными кнопками (обрабатываются по точному тексту)
    print("🔍 MAIN: Регистрируем payments.router")
    dp.include_router(payments.router)    # "💳 Купить подписку" + callback queries
    print("🔍 MAIN: payments.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем promocodes.router")
    dp.include_router(promocodes.router) # "🎟 Ввести промокод" + состояния
    print("🔍 MAIN: promocodes.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем help.router")
    dp.include_router(help.router)       # "❓ Помощь"
    print("🔍 MAIN: help.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем search.router")
    dp.include_router(search.router)     # "🔍 Найти объявления"
    print("🔍 MAIN: search.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем list_items.router")
    dp.include_router(list_items.router) # "📋 Мои отслеживаемые"
    print("🔍 MAIN: list_items.router зарегистрирован")
    
    print("🔍 MAIN: Регистрируем remove.router")
    dp.include_router(remove.router)    # "🗑️ Удалить объявление" + callback queries
    print("🔍 MAIN: remove.router зарегистрирован")
    
    # 3. Универсальный роутер в конце (обрабатывает все остальные сообщения)
    # ВРЕМЕННО ОТКЛЮЧАЕМ для отладки кнопок
    # print("🔍 MAIN: Регистрируем messages.router (универсальный обработчик)")
    # dp.include_router(messages.router)
    
    print("🔍 MAIN: Все роутеры зарегистрированы успешно")
    

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
