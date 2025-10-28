"""
HTTP клиент для взаимодействия с parse_avito сервисом
"""
import httpx
from typing import Optional, List, Dict
from app.config import PARSE_AVITO_BASE_URL


class ParseAvitoClient:
    """Клиент для взаимодействия с parse_avito API"""
    
    def __init__(self, base_url: str = PARSE_AVITO_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def add_filter(
        self,
        telegram_id: str,
        search_query: Optional[str] = None,
        category_id: Optional[int] = None,
        location_id: Optional[int] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None
    ) -> Dict:
        """Добавить новый фильтр для пользователя"""
        response = await self.client.post(
            f"{self.base_url}/api/add_filter",
            json={
                "telegram_id": telegram_id,
                "search_query": search_query,
                "category_id": category_id,
                "location_id": location_id,
                "price_from": price_from,
                "price_to": price_to
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def update_filter(
        self,
        filter_id: str,
        search_query: Optional[str] = None,
        category_id: Optional[int] = None,
        location_id: Optional[int] = None,
        price_from: Optional[int] = None,
        price_to: Optional[int] = None
    ) -> Dict:
        """Обновить фильтр"""
        response = await self.client.post(
            f"{self.base_url}/api/update_filter",
            json={
                "filter_id": filter_id,
                "search_query": search_query,
                "category_id": category_id,
                "location_id": location_id,
                "price_from": price_from,
                "price_to": price_to
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def delete_filter(self, filter_id: str) -> Dict:
        """Удалить фильтр"""
        response = await self.client.post(
            f"{self.base_url}/api/delete_filter",
            json={"filter_id": filter_id}
        )
        response.raise_for_status()
        return response.json()
    
    async def deactivate_filters(self, telegram_id: str) -> Dict:
        """Деактивировать все фильтры для пользователя"""
        response = await self.client.post(
            f"{self.base_url}/api/deactivate_filters",
            json={"telegram_id": telegram_id}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_user_filters(self, telegram_id: str) -> Dict:
        """Получить все активные фильтры пользователя"""
        response = await self.client.get(
            f"{self.base_url}/api/get_user_filters",
            params={"telegram_id": telegram_id}
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Закрыть клиент"""
        await self.client.aclose()


# Глобальный экземпляр клиента
parse_avito_client = ParseAvitoClient()

