"""
Управление отслеживаемыми объявлениями
"""
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db import get_user_tracked_items, remove_tracked_item
from app.config import MAX_ITEMS_PER_USER, CHECK_INTERVAL
from app.avito_api import AvitoAPI
import re

router = Router()
api = AvitoAPI()

def _build_remove_keyboard(tracked_items):
    rows = []
    for i, item in enumerate(tracked_items, 1):
        rows.append([InlineKeyboardButton(text=f"Удалить {i}", callback_data=f"rm:{item.item_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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


@router.message(lambda message: message.text not in {
    # Команды
    "/start", "/help", "/search", "/list", "/remove", "/admin",
    
    # Кнопки интерфейса
    "💳 Купить подписку", "🎟 Ввести промокод", "❓ Помощь",
    "🔍 Найти объявления", "📋 Мои отслеживаемые", "🗑️ Удалить объявление",
    
    # Кнопки отмены
    "❌ Отменить ввод", "❌ Отменить создание",
    
    # Админские кнопки
    "📦 Подписки", "🎟 Промокоды", "➕ Создать подписку", 
    "🗑 Удалить подписку", "➕ Создать промокод", "🗑 Удалить промокод",
    "◀️ Назад к админке", "◀️ Назад",
    
    # Кнопки управления
    "⚙️ Управление"
})
async def handle_add_item(message: types.Message):
    """Обработчик добавления объявления по ID"""
    text = message.text.strip() if message.text else "[НЕТ ТЕКСТА]"
    user_id = message.from_user.id
    
    # Проверяем активную подписку
    from app.db import user_has_active_subscription
    has_sub = await user_has_active_subscription(str(user_id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской. Нажмите '💳 Купить подписку'.")
        return

    # Обрабатываем только числовые ID
    if not re.match(r"^\d+$", text):
        return
    
    try:
        # Проверяем текущие отслеживаемые объявления
        tracked_items = await get_user_tracked_items(str(user_id))
        if len(tracked_items) >= MAX_ITEMS_PER_USER:
            await message.answer(f"Достигнут лимит отслеживаемых объявлений ({MAX_ITEMS_PER_USER}).")
            return

        # Получаем детали объявления
        item_details = await api.get_item_details(text)
        if not item_details:
            await message.answer("Объявление не найдено.")
            return

        price = float(item_details.get("price", 0))
        title = item_details.get("title", "")
        
        # Добавляем в БД
        from app.db import add_tracked_item
        await add_tracked_item(str(user_id), text, price, title)
        
        await message.answer(
            f"✅ Объявление добавлено в отслеживание!\n"
            f"📌 {title}\n"
            f"💰 Текущая цена: {price:,.2f} ₽\n"
            f"🔄 Проверка каждые {CHECK_INTERVAL // 60} минут"
        )
    except ValueError as e:
        if "already tracked" in str(e):
            await message.answer("Это объявление уже отслеживается.")
        else:
            await message.answer("Ошибка при добавлении объявления.")
    except Exception as e:
        print(f"Ошибка при добавлении объявления: {e}")
        await message.answer("Ошибка при добавлении объявления.")
