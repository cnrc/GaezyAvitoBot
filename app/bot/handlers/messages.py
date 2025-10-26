import re
from aiogram import Router, types
from app.config import MAX_ITEMS_PER_USER, CHECK_INTERVAL, PRICE_CHANGE_THRESHOLD
from app.db import user_has_active_subscription, get_user_tracked_items, add_tracked_item
from app.avito_api import AvitoAPI

router = Router()
api = AvitoAPI()

@router.message(lambda message: message.text not in {
    # Команды
    "/start", "/help", "/search", "/list", "/remove", "/admin",
    
    # Кнопки интерфейса
    "💳 Купить подписку", "🎟 Ввести промокод", "❓ Помощь",
    "🔍 Найти объявления", "📋 Мои отслеживаемые", "🗑️ Удалить объявление",
    
    # Админские кнопки
    "📦 Подписки", "🎟 Промокоды", "➕ Создать подписку", 
    "🗑 Удалить подписку", "➕ Создать промокод", "🗑 Удалить промокод",
    "◀️ Назад к админке", "◀️ Назад",
    
    # Кнопки управления
    "⚙️ Управление"
})
async def handle_message(message: types.Message):
    text = message.text.strip() if message.text else "[НЕТ ТЕКСТА]"
    user_id = message.from_user.id
    
    print(f"🔍 UNIVERSAL DEBUG: Получено сообщение от пользователя {user_id}")
    print(f"🔍 UNIVERSAL DEBUG: Текст сообщения: '{text}'")
    print(f"🔍 UNIVERSAL DEBUG: Тип сообщения: {message.content_type}")
    print(f"MESSAGES HANDLER: Обрабатываем сообщение '{text}' от пользователя {user_id}")

    # Блокируем функционал для пользователей без активной подписки
    # (только для обычных сообщений, не для команд и кнопок)
    has_sub = await user_has_active_subscription(str(user_id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской. Нажмите '💳 Купить подписку'.")
        return

    # Обработка команды-перекрытия удаления: если ожидается удаление, handled in remove.py
    # Парсинг запроса с разделителем '|'
    if "|" in text:
        params = [p.strip() for p in text.split("|")]
        search_query = params[0]
        category = params[1] if len(params) > 1 else None
        location = params[2] if len(params) > 2 else None
        price_from = int(params[3]) if len(params) > 3 and params[3].isdigit() else None
        price_to = int(params[4]) if len(params) > 4 and params[4].isdigit() else None

        await _perform_search(message, search_query, category, location, price_from, price_to)
        return

    # Обработка ID объявления (только числа)
    if re.match(r"^\d+$", text):
        try:
            # Проверяем текущие отслеживаемые объявления
            tracked_items = await get_user_tracked_items(str(user_id))
            if len(tracked_items) >= MAX_ITEMS_PER_USER:
                await message.answer(f"Достигнут лимит отслеживаемых объявлений ({MAX_ITEMS_PER_USER}).")
                return

            item_details = await api.get_item_details(text)
            if not item_details:
                await message.answer("Объявление не найдено.")
                return

            price = float(item_details.get("price", 0))
            title = item_details.get("title", "")
            
            # Добавляем в БД
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
        return

async def _perform_search(message: types.Message, query: str, category: str=None, location: str=None, price_from: int=None, price_to: int=None):
    try:
        # Получаем id категории и локации при необходимости
        category_id = None
        if category:
            categories = await api.get_categories()
            category_id = next((c['id'] for c in categories if c.get('name','').lower() == category.lower()), None)

        location_id = None
        if location:
            locations = await api.get_locations(location)
            location_id = next((l['id'] for l in locations if l.get('name','').lower() == location.lower()), None)

        results = await api.search_items(
            category_id=category_id,
            location_id=location_id,
            search_query=query,
            price_from=price_from,
            price_to=price_to
        )

        if not results or not results.get('items'):
            await message.answer("По вашему запросу ничего не найдено.")
            return

        msg = "Результаты поиска:\n\n"
        for item in results['items'][:5]:
            price = float(item.get('price', 0))
            msg += (
                f"📌 {item.get('title','')}\n"
                f"💰 Цена: {price:,.2f} ₽\n"
                f"📍 {item.get('location','Не указано')}\n"
                f"🔗 ID: {item.get('id')}\n\n"
            )
        msg += "\nЧтобы отслеживать объявление, отправьте его ID"
        await message.answer(msg)
    except Exception:
        await message.answer("Произошла ошибка при поиске объявлений.")
