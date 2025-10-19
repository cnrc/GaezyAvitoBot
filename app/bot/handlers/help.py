from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "Как использовать бота:\n"
        "• Отправьте ID объявления для отслеживания\n"
        "• Используйте /search для поиска\n\n"
        "Команды:\n"
        "/search — поиск объявлений\n"
        "/list — показать отслеживаемые объявления\n"
        "/remove — удалить отслеживаемое объявление"
    )
