from aiogram import Router, types
from app.utils.storage import user_items
from aiogram.filters import Command

router = Router()

@router.message(Command("list"))
async def list_items(message: types.Message):
    user_id = message.from_user.id
    items = user_items.get(user_id, {})

    if not items:
        await message.answer("У вас нет отслеживаемых объявлений.")
        return

    msg = "Ваши отслеживаемые объявления:\n\n"
    for i, (item_id, price) in enumerate(items.items(), 1):
        msg += f"{i}. ID: {item_id} — {price:,.2f} ₽\n"

    await message.answer(msg)
