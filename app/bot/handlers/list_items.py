from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.utils.storage import user_items

router = Router()

@router.message(lambda message: message.text == "📋 Мои отслеживаемые")
async def list_items_via_button(message: types.Message):
    user_id = message.from_user.id
    items = user_items.get(user_id, {})

    if not items:
        await message.answer("📋 У вас нет отслеживаемых объявлений.")
        return

    msg = "📋 <b>Ваши отслеживаемые объявления:</b>\n\n"
    keyboard_rows = []
    for i, (item_id, price) in enumerate(items.items(), 1):
        msg += f"{i}. ID: {item_id} — {price:,.2f} ₽\n"
        keyboard_rows.append([
            InlineKeyboardButton(text=f"Удалить {i}", callback_data=f"rm:{item_id}")
        ])

    await message.answer(
        msg,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )
