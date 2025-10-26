from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db import get_user_tracked_items

router = Router()

@router.message(lambda message: message.text == "📋 Мои отслеживаемые")
async def list_items_via_button(message: types.Message):
    user_id = str(message.from_user.id)
    tracked_items = await get_user_tracked_items(user_id)

    if not tracked_items:
        await message.answer("📋 У вас нет отслеживаемых объявлений.")
        return

    msg = "📋 <b>Ваши отслеживаемые объявления:</b>\n\n"
    keyboard_rows = []
    for i, item in enumerate(tracked_items, 1):
        title = item.last_title or "Без названия"
        price = item.last_price or 0
        msg += f"{i}. 📌 {title}\n"
        msg += f"   💰 {price:,.2f} ₽\n"
        msg += f"   🔗 ID: {item.item_id}\n\n"
        keyboard_rows.append([
            InlineKeyboardButton(text=f"Удалить {i}", callback_data=f"rm:{item.item_id}")
        ])

    await message.answer(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )
