from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "Привет! Я бот для мониторинга объявлений на Авито.\n\n"
        "Вы можете отправить:\n"
        "1️⃣ ID объявления для отслеживания цены\n"
        "2️⃣ Поисковый запрос для мониторинга новых объявлений\n\n"
        "Команды:\n"
        "/search — поиск объявлений\n"
        "/list — ваши отслеживаемые объявления\n"
        "/remove — удалить из списка\n"
        "/help — справка"
    )
