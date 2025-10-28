"""
Поиск объявлений на Avito
"""
from aiogram import Router, types
from app.db import user_has_active_subscription
from app.parse_avito_client import parse_avito_client

router = Router()



@router.message(lambda message: "|" in message.text if message.text else False)
async def handle_tracking_by_filters(message: types.Message):
    """Обработчик добавления отслеживания по фильтрам"""
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    text = message.text.strip()
    if "|" not in text:
        return
    
    params = [p.strip() for p in text.split("|")]
    search_query = params[0] if params[0] else None
    category = params[1] if len(params) > 1 and params[1] else None
    location = params[2] if len(params) > 2 and params[2] else None
    price_from = int(params[3]) if len(params) > 3 and params[3].isdigit() else None
    price_to = int(params[4]) if len(params) > 4 and params[4].isdigit() else None
    
    try:
        # Получаем ID категории и локации
        category_id = None
        location_id = None
        
        # TODO: получать категории и локации через API если нужно
        if category:
            category_id = category
        
        if location:
            location_id = location
        
        # Добавляем отслеживание через parse_avito
        response = await parse_avito_client.add_filter(
            telegram_id=str(message.from_user.id),
            search_query=search_query,
            category_id=category_id,
            location_id=location_id,
            price_from=price_from,
            price_to=price_to
        )
        
        await message.answer(
            "✅ <b>Фильтр добавлен!</b>\n\n"
            "Сервис будет отслеживать новые объявления по заданным параметрам и отправлять их раз в минуту.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"Ошибка при добавлении фильтра: {e}")
        await message.answer(f"Ошибка при добавлении фильтра: {str(e)}")


