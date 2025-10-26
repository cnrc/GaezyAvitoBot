import asyncio
from aiogram import Bot
from app.db import get_all_active_tracked_items, get_all_active_tracked_searches, update_tracked_item_state, update_tracked_search_state, AsyncSessionLocal, TrackedItem
from sqlalchemy import select
from app.avito_api import AvitoAPI
from app.config import PRICE_CHANGE_THRESHOLD, CHECK_INTERVAL
from datetime import datetime

api = AvitoAPI()


async def check_tracked_items(bot: Bot):
    """Проверка конкретных объявлений по ID"""
    tracked_items = await get_all_active_tracked_items()
    
    for tracked_item in tracked_items:
        try:
            # Получаем пользователя один раз
            from app.db import User
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.id == tracked_item.user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    continue
            
            item_details = await api.get_item_details(tracked_item.item_id)
            
            # Если объявление удалено
            if not item_details:
                # Архивируем объявление
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(TrackedItem).where(TrackedItem.id == tracked_item.id)
                    )
                    item = result.scalar_one_or_none()
                    if item:
                        item.is_active = False
                        await session.commit()
                
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=f"❌ Объявление {tracked_item.item_id} больше не доступно и удалено из отслеживания"
                )
                continue
            
            current_price = float(item_details.get('price', 0))
            current_title = item_details.get('title', '')
            current_description = item_details.get('description', '')
            
            price_changed = False
            title_changed = False
            description_changed = False
            
            # Проверяем изменения цены
            if tracked_item.last_price is not None and current_price != tracked_item.last_price:
                price_change = ((current_price - tracked_item.last_price) / tracked_item.last_price) * 100 if tracked_item.last_price > 0 else 0
                if abs(price_change) >= PRICE_CHANGE_THRESHOLD:
                    price_changed = True
                    direction = "выросла" if current_price > tracked_item.last_price else "снизилась"
                    await bot.send_message(
                        chat_id=int(user.telegram_id),
                        text=(
                            f"🚨 Изменение цены в объявлении!\n"
                            f"ID: {tracked_item.item_id}\n"
                            f"Название: {current_title}\n"
                            f"Цена {direction} на {abs(price_change):.2f}%\n"
                            f"С {tracked_item.last_price:,.2f} ₽ до {current_price:,.2f} ₽"
                        )
                    )
            
            # Проверяем изменения названия
            if tracked_item.last_title and current_title != tracked_item.last_title:
                title_changed = True
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=(
                        f"📝 Изменение названия объявления!\n"
                        f"ID: {tracked_item.item_id}\n"
                        f"Старое: {tracked_item.last_title}\n"
                        f"Новое: {current_title}"
                    )
                )
            
            # Проверяем изменения описания
            if tracked_item.last_description and current_description != tracked_item.last_description:
                description_changed = True
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=(
                        f"📝 Изменение описания объявления!\n"
                        f"ID: {tracked_item.item_id}\n"
                        f"Название: {current_title}"
                    )
                )
            
            # Обновляем состояние в БД
            if price_changed or title_changed or description_changed:
                await update_tracked_item_state(
                    tracked_item,
                    price=current_price,
                    title=current_title,
                    description=current_description
                )
                
        except Exception as e:
            print(f"Ошибка при проверке объявления {tracked_item.item_id}: {e}")
            continue


async def check_tracked_searches(bot: Bot):
    """Проверка новых объявлений по фильтрам"""
    tracked_searches = await get_all_active_tracked_searches()
    
    for tracked_search in tracked_searches:
        try:
            # Получаем пользователя для отправки уведомления
            from app.db import User
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.id == tracked_search.user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    continue
            
            # Выполняем поиск
            results = await api.search_items(
                category_id=tracked_search.category_id,
                location_id=tracked_search.location_id,
                search_query=tracked_search.search_query,
                price_from=tracked_search.price_from,
                price_to=tracked_search.price_to,
                sort_by="date",
                per_page=50
            )
            
            if not results or not results.get('items'):
                continue
            
            # Получаем ID текущих найденных объявлений
            current_item_ids = [str(item.get('id', '')) for item in results['items']]
            last_found_ids = tracked_search.last_found_item_ids or []
            
            # Находим новые объявления
            new_item_ids = [item_id for item_id in current_item_ids if item_id not in last_found_ids]
            
            # Отправляем уведомления о новых объявлениях
            for item_id in new_item_ids[:10]:  # Максимум 10 новых объявлений за раз
                try:
                    item_details = await api.get_item_details(item_id)
                    if item_details:
                        price = float(item_details.get('price', 0))
                        title = item_details.get('title', 'Нет названия')
                        location = item_details.get('location', 'Не указано')
                        
                        await bot.send_message(
                            chat_id=int(user.telegram_id),
                            text=(
                                f"🆕 Новое объявление по вашему запросу!\n"
                                f"📌 {title}\n"
                                f"💰 Цена: {price:,.2f} ₽\n"
                                f"📍 {location}\n"
                                f"🔗 ID: {item_id}"
                            )
                        )
                except Exception as e:
                    print(f"Ошибка при отправке уведомления о новом объявлении: {e}")
                    continue
            
            # Обновляем состояние в БД
            if new_item_ids:
                await update_tracked_search_state(tracked_search, current_item_ids)
                
        except Exception as e:
            print(f"Ошибка при проверке поиска {tracked_search.id}: {e}")
            continue


async def check_prices(bot: Bot):
    """Главная функция проверки - проверяет и объявления, и поиски"""
    await check_tracked_items(bot)
    await check_tracked_searches(bot)
