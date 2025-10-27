"""
Поиск объявлений на Avito
"""
from aiogram import Router, types
from app.db import user_has_active_subscription
from app.avito_api import AvitoAPI

router = Router()
api = AvitoAPI()

@router.message(lambda message: message.text == "🔍 Найти объявления")
async def search_via_button(message: types.Message):
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской. Нажмите '💳 Купить подписку'.")
        return
    
    await message.answer(
        "🔍 <b>Поиск объявлений</b>\n\n"
        "Введите параметры в формате:\n"
        "Запрос | Категория | Город | Цена от | Цена до\n\n"
        "Например: iPhone 13 | Электроника | Москва | 50000 | 80000",
        parse_mode="HTML"
    )


@router.message(lambda message: "|" in message.text if message.text else False)
async def handle_search(message: types.Message):
    """Обработчик поиска объявлений"""
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        return
    
    text = message.text.strip()
    if "|" not in text:
        return
    
    params = [p.strip() for p in text.split("|")]
    search_query = params[0]
    category = params[1] if len(params) > 1 else None
    location = params[2] if len(params) > 2 else None
    price_from = int(params[3]) if len(params) > 3 and params[3].isdigit() else None
    price_to = int(params[4]) if len(params) > 4 and params[4].isdigit() else None

    await _perform_search(message, search_query, category, location, price_from, price_to)


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
    except Exception as e:
        print(f"Ошибка при поиске: {e}")
        await message.answer("Произошла ошибка при поиске объявлений.")


