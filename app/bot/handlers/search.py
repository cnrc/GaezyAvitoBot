from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("search"))
async def search_command(message: types.Message):
    await message.answer(
        "Введите параметры поиска в формате:\n"
        "Запрос | Категория | Город | Цена от | Цена до\n\n"
        "Например: iPhone 13 | Электроника | Москва | 50000 | 80000\n"
        "Или просто введите поисковый запрос"
    )
