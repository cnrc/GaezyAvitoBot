from aiogram import Router, types

router = Router()

@router.message(lambda message: message.text == "🔍 Найти объявления")
async def search_via_button(message: types.Message):
    await message.answer(
        "🔍 <b>Поиск объявлений</b>\n\n"
        "Введите параметры в формате:\n"
        "Запрос | Категория | Город | Цена от | Цена до\n\n"
        "Например: iPhone 13 | Электроника | Москва | 50000 | 80000",
        parse_mode="HTML"
    )
