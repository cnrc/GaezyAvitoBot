from aiogram import Router, types
from app.utils.storage import user_items
from aiogram.filters import Command

router = Router()

@router.message(Command("remove"))
async def remove_command(message: types.Message):
    user_id = message.from_user.id
    items = user_items.get(user_id, {})
    if not items:
        await message.answer("У вас нет отслеживаемых объявлений.")
        return

    msg = "Выберите номер объявления для удаления:\n\n"
    for i, (item_id, price) in enumerate(items.items(), 1):
        msg += f"{i}. ID: {item_id} — {price:,.2f} ₽\n"
    await message.answer(msg)

@router.message()
async def remove_item_by_number(message: types.Message):
    # Обработчик числового сообщения для удаления объявления
    text = message.text.strip()
    if not text.isdigit():
        return
    user_id = message.from_user.id
    if user_id not in user_items or not user_items[user_id]:
        await message.answer("У вас нет отслеживаемых объявлений.")
        return

    try:
        index = int(text) - 1
        items = list(user_items[user_id].items())
        if 0 <= index < len(items):
            item_id, _ = items[index]
            del user_items[user_id][item_id]
            await message.answer(f"✅ Объявление {item_id} удалено.")
        else:
            await message.answer("Неверный номер.")
    except Exception:
        await message.answer("Ошибка при удалении.")
