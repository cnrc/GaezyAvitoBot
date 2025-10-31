"""
Сервис для отслеживания объявлений и уведомлений пользователей
"""
import asyncio
import logging
from typing import Dict, Any, List
from aiogram import Bot
from app.services.parser_api import parser_client
from app.db.repository import (
    get_active_trackings_for_subscribed_users, 
    filter_new_ads_for_tracking,
    mark_ads_as_seen
)

logger = logging.getLogger(__name__)

class TrackingService:
    """Сервис для отслеживания новых объявлений"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        
    async def start_tracking(self):
        """Запускает периодическое отслеживание объявлений"""
        if self.running:
            logger.warning("Отслеживание уже запущено")
            return
            
        self.running = True
        logger.info("🚀 Запуск сервиса отслеживания объявлений")
        
        while self.running:
            try:
                await self.check_new_ads()
                await asyncio.sleep(60)  # Ждем 1 минуту
            except Exception as e:
                logger.error(f"Ошибка в цикле отслеживания: {e}")
                await asyncio.sleep(60)  # Ждем минуту перед следующей попыткой
                
    async def stop_tracking(self):
        """Останавливает отслеживание"""
        logger.info("🛑 Остановка сервиса отслеживания объявлений")
        self.running = False
        
    async def check_new_ads(self):
        """Проверяет новые объявления и отправляет уведомления"""
        logger.info("🔍 Проверка новых объявлений...")
        
        try:
            # Получаем отслеживания пользователей с активной подпиской
            users_trackings = await get_active_trackings_for_subscribed_users()
            
            if not users_trackings:
                logger.info("Нет активных отслеживаний для пользователей с подпиской")
                return
                
            # Обрабатываем каждый фильтр отдельно
            for telegram_id, trackings in users_trackings.items():
                for tracking in trackings:
                    await self.process_tracking(tracking, telegram_id)
                
        except Exception as e:
            logger.error(f"Ошибка при проверке новых объявлений: {e}")
            import traceback
            traceback.print_exc()
            
    async def process_tracking(self, tracking: Dict[str, Any], telegram_id: str):
        """Обрабатывает один фильтр отслеживания"""
        try:
            tracking_id = tracking['id']
            tracking_name = tracking['name']
            link = tracking['link']
            min_price = tracking.get('min_price')  # Может быть None
            max_price = tracking.get('max_price')  # Может быть None
            
            logger.info(f"Парсинг фильтра {tracking_id} для пользователя {telegram_id}")
            logger.info(f"URL: {link[:50]}... (цена: {min_price}-{max_price})")
            
            # Отправляем запрос на парсинг для этого фильтра
            result = await parser_client.parse_ads(
                urls=[link],
                min_price=min_price,
                max_price=max_price
            )
            
            if not result or not result.get('success'):
                logger.warning(f"Неуспешный результат парсинга для фильтра {tracking_id}")
                return
                
            ads = result.get('ads', [])
            if not ads:
                logger.info(f"Новых объявлений не найдено для фильтра {tracking_id}")
                return
            
            # Логируем первые несколько объявлений для отладки
            logger.debug(f"Получено {len(ads)} объявлений, первое: {ads[0] if ads else 'нет'}")
            
            # Фильтруем только новые объявления (проверяем в БД)
            new_ads = await filter_new_ads_for_tracking(str(tracking_id), ads)
            
            if not new_ads:
                logger.info(f"Все объявления уже были показаны для фильтра {tracking_id}")
                return
                
            logger.info(f"Найдено {len(new_ads)} новых объявлений для фильтра {tracking_id}")
            
            # Отправляем уведомления пользователю
            for ad in new_ads:
                await self.send_ad_notification(telegram_id, ad, tracking_name)
            
            # Помечаем объявления как просмотренные для этого фильтра
            try:
                await mark_ads_as_seen(str(tracking_id), new_ads)
            except Exception as save_error:
                logger.error(f"Ошибка при сохранении объявлений в БД: {save_error}")
                import traceback
                traceback.print_exc()
                # Продолжаем работу, не прерывая весь процесс
                
        except Exception as e:
            logger.error(f"Ошибка при обработке фильтра {tracking.get('id', 'unknown')}: {e}")
            import traceback
            traceback.print_exc()
            
    async def send_ad_notification(self, telegram_id: str, ad: Dict[str, Any], tracking_name: str = None):
        """Отправляет уведомление о конкретном объявлении"""
        try:
            ad_id = ad['id']
            price = ad['price']
            
            # Формируем сообщение
            message = (
                "🔔 <b>Найдено новое объявление</b>\n\n"
                f"💰 Цена: <b>{price:,} ₽</b>\n"
                f"🔗 Ссылка: https://www.avito.ru/{ad_id}\n"
            )
            
            if tracking_name:
                message += f"📂 Отслеживание: <i>{tracking_name}</i>\n"
                
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            
            logger.info(f"Отправлено уведомление пользователю {telegram_id} об объявлении {ad_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id} об объявлении {ad.get('id')}: {e}")

# Глобальная переменная для сервиса отслеживания
tracking_service = None

def init_tracking_service(bot: Bot):
    """Инициализирует глобальный сервис отслеживания"""
    global tracking_service
    tracking_service = TrackingService(bot)
    return tracking_service
