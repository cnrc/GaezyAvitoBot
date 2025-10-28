import asyncio
from aiogram import Bot
from app.db import get_all_active_tracked_items, AsyncSessionLocal, TrackedItem
from sqlalchemy import select
from app.config import PRICE_CHANGE_THRESHOLD, CHECK_INTERVAL
from datetime import datetime

# Мониторинг по фильтрам теперь выполняет parse_avito сервис


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
            
            # TODO: добавить парсинг через внешний API
            item_details = None
            
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
    """Проверка новых объявлений по фильтрам - теперь выполняется parse_avito сервисом"""
    # Мониторинг по фильтрам теперь выполняется в parse_avito
    pass


async def check_prices(bot: Bot):
    """Главная функция проверки - проверяет только объявления по ID"""
    # Мониторинг по фильтрам выполняется parse_avito
    await check_tracked_items(bot)
