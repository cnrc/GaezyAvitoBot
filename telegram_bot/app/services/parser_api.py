"""
API клиент для взаимодействия с сервисом парсинга Avito
"""
import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.config import PARSER_API_URL, PARSER_API_TOKEN

logger = logging.getLogger(__name__)

class ParserAPIClient:
    """Клиент для взаимодействия с API парсинга"""
    
    def __init__(self):
        self.api_url = PARSER_API_URL
        self.api_token = PARSER_API_TOKEN
        
    async def parse_ads(self, urls: List[str], min_price: int = 0, max_price: int = 0) -> Optional[Dict[str, Any]]:
        """
        Отправляет запрос на парсинг объявлений
        
        Args:
            urls: Список URL для парсинга
            min_price: Минимальная цена
            max_price: Максимальная цена
            
        Returns:
            Ответ API или None в случае ошибки
        """
        if not self.api_token:
            logger.error("PARSER_API_TOKEN не установлен в конфигурации")
            return None
            
        if not self.api_url:
            logger.error("PARSER_API_URL не установлен в конфигурации")
            return None
            
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "urls": urls,
            "min_price": min_price,
            "max_price": max_price
        }
        
        max_retries = 2  # Дополнительная попытка при таймауте
        timeout_seconds = 60  # Увеличиваем таймаут до 60 секунд
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    logger.info(f"[Попытка {attempt + 1}/{max_retries}] Отправляем запрос на парсинг: {len(urls)} URLs, цена: {min_price}-{max_price}")
                    
                    async with session.post(
                        self.api_url,
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=timeout_seconds)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Успешно получен ответ: найдено {data.get('total_found', 0)} объявлений")
                            # Логируем структуру объявлений для отладки
                            if data.get('ads'):
                                logger.debug(f"Первое объявление из ответа: {data['ads'][0]}")
                            return data
                        else:
                            error_text = await response.text()
                            logger.error(f"Ошибка API парсинга: {response.status} - {error_text}")
                            return None
                            
            except asyncio.TimeoutError:
                logger.warning(f"[Попытка {attempt + 1}/{max_retries}] Таймаут при запросе к API парсинга ({timeout_seconds}с)")
                if attempt < max_retries - 1:
                    logger.info(f"Повторяем запрос через 5 секунд...")
                    await asyncio.sleep(5)
                else:
                    logger.error(f"Все {max_retries} попыток завершились таймаутом. API доступен по адресу: {self.api_url}")
                    return None
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка сети при обращении к API парсинга: {e}")
                return None
            except Exception as e:
                logger.error(f"Неожиданная ошибка при запросе к API парсинга: {e}")
                import traceback
                traceback.print_exc()
                return None
                
        return None

# Глобальный экземпляр клиента
parser_client = ParserAPIClient()
