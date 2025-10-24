from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.utils.storage import user_items

router = Router()

def _build_remove_keyboard(items_dict):
    rows = []
    for i, (item_id, _) in enumerate(items_dict.items(), 1):
        rows.append([InlineKeyboardButton(text=f"Удалить {i}", callback_data=f"rm:{item_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(lambda message: message.text == "🗑️ Удалить объявление")
async def remove_menu(message: types.Message):
    user_id = message.from_user.id
    items = user_items.get(user_id, {})
    if not items:
        await message.answer("У вас нет отслеживаемых объявлений.")
        return

    msg = "Выберите объявление для удаления:"\
        + "\n\n" + "\n".join(
            f"{i}. ID: {item_id} — {price:,.2f} ₽" for i, (item_id, price) in enumerate(items.items(), 1)
        )
    await message.answer(msg, reply_markup=_build_remove_keyboard(items))

@router.callback_query(F.data.startswith("rm:"))
async def handle_remove_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    item_id = callback.data.split(":", 1)[1]

    if user_id not in user_items or item_id not in user_items[user_id]:
        await callback.answer("Не найдено", show_alert=False)
        return

    try:
        del user_items[user_id][item_id]
        await callback.answer("Удалено")
        # Обновляем сообщение со списком
        items = user_items.get(user_id, {})
        if not items:
            await callback.message.edit_text("Все объявления удалены.")
        else:
            msg = "Выберите объявление для удаления:"\
                + "\n\n" + "\n".join(
                    f"{i}. ID: {iid} — {price:,.2f} ₽" for i, (iid, price) in enumerate(items.items(), 1)
                )
            await callback.message.edit_text(msg, reply_markup=_build_remove_keyboard(items))
    except Exception:
        await callback.answer("Ошибка", show_alert=False)
