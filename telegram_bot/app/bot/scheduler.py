import asyncio
from aiogram import Bot
from app.db import get_all_active_tracked_items, AsyncSessionLocal, Tracked, User
from sqlalchemy import select
from datetime import datetime

# Мониторинг по фильтрам теперь выполняет parse_avito сервис


async def check_tracked_items(bot: Bot):
    """Проверка конкретных объявлений по ссылкам"""
    tracked_items = await get_all_active_tracked_items()
    
    for tracked_item in tracked_items:
        try:
            # Получаем пользователя
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.id == tracked_item.user_id)
                )
                user = result.scalar_one_or_none()
                if not user:
                    continue
            
            # TODO: Интеграция с парсером Avito для получения данных объявления
            # Пока что эта функция не активна, так как нужно интегрировать
            # с parser_avito для получения актуальных данных по ссылке
            
            # item_details = await parse_avito_item(tracked_item.link)
            item_details = None
            
            # Если не удалось получить данные объявления
            if not item_details:
                # Пока не архивируем автоматически, так как это может быть
                # временная проблема с парсером
                print(f"🔍 Не удалось получить данные для {tracked_item.link}")
                continue
            
            current_price = float(item_details.get('price', 0))
            current_title = item_details.get('title', '')
            
            # Проверяем ценовые фильтры пользователя
            price_in_range = True
            
            if tracked_item.min_price and current_price < tracked_item.min_price:
                price_in_range = False
                
            if tracked_item.max_price and current_price > tracked_item.max_price:
                price_in_range = False
            
            # Если цена не в диапазоне, отправляем уведомление
            if not price_in_range:
                range_text = ""
                if tracked_item.min_price and tracked_item.max_price:
                    range_text = f"(ваш диапазон: {tracked_item.min_price:,.0f} - {tracked_item.max_price:,.0f} ₽)"
                elif tracked_item.min_price:
                    range_text = f"(ваш минимум: {tracked_item.min_price:,.0f} ₽)"
                elif tracked_item.max_price:
                    range_text = f"(ваш максимум: {tracked_item.max_price:,.0f} ₽)"
                
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=(
                        f"💰 <b>Изменение цены!</b>\n\n"
                        f"📋 {current_title}\n"
                        f"💵 Новая цена: {current_price:,.0f} ₽ {range_text}\n"
                        f"🔗 {tracked_item.link}"
                    ),
                    parse_mode="HTML"
                )
            
            # Обновляем время последней проверки
            from app.db import update_tracked_item_state
            await update_tracked_item_state(tracked_item)
                
        except Exception as e:
            print(f"Ошибка при проверке объявления {tracked_item.link}: {e}")
            continue


async def check_tracked_searches(bot: Bot):
    """Проверка новых объявлений по фильтрам - теперь выполняется parse_avito сервисом"""
    # Мониторинг по фильтрам теперь выполняется в parse_avito
    pass


async def check_prices(bot: Bot):
    """Главная функция проверки - проверяет только объявления по ID"""
    # Мониторинг по фильтрам выполняется parse_avito
    await check_tracked_items(bot)
