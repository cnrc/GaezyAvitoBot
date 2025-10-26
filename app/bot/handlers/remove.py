from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db import get_user_tracked_items, remove_tracked_item

router = Router()

def _build_remove_keyboard(tracked_items):
    rows = []
    for i, item in enumerate(tracked_items, 1):
        rows.append([InlineKeyboardButton(text=f"Удалить {i}", callback_data=f"rm:{item.item_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(lambda message: message.text == "🗑️ Удалить объявление")
async def remove_menu(message: types.Message):
    user_id = str(message.from_user.id)
    tracked_items = await get_user_tracked_items(user_id)
    
    if not tracked_items:
        await message.answer("У вас нет отслеживаемых объявлений.")
        return

    msg = "Выберите объявление для удаления:\n\n"
    for i, item in enumerate(tracked_items, 1):
        title = item.last_title or "Без названия"
        price = item.last_price or 0
        msg += f"{i}. {title} — {price:,.2f} ₽\n"
        msg += f"   ID: {item.item_id}\n\n"
    
    await message.answer(msg, reply_markup=_build_remove_keyboard(tracked_items))

@router.callback_query(F.data.startswith("rm:"))
async def handle_remove_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    item_id = callback.data.split(":", 1)[1]

    try:
        # Удаляем из БД (архивируем)
        success = await remove_tracked_item(user_id, item_id)
        
        if not success:
            await callback.answer("Объявление не найдено", show_alert=False)
            return
        
        await callback.answer("Удалено")
        
        # Обновляем сообщение со списком
        tracked_items = await get_user_tracked_items(user_id)
        if not tracked_items:
            await callback.message.edit_text("Все объявления удалены.")
        else:
            msg = "Выберите объявление для удаления:\n\n"
            for i, item in enumerate(tracked_items, 1):
                title = item.last_title or "Без названия"
                price = item.last_price or 0
                msg += f"{i}. {title} — {price:,.2f} ₽\n"
                msg += f"   ID: {item.item_id}\n\n"
            
            await callback.message.edit_text(msg, reply_markup=_build_remove_keyboard(tracked_items))
    except Exception as e:
        print(f"Ошибка при удалении: {e}")
        await callback.answer("Ошибка", show_alert=False)
