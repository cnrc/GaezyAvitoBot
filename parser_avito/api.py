"""
FastAPI приложение для парсера Авито

Предоставляет REST API для парсинга объявлений с Авито с аутентификацией по токену.
Эндпоинт /parse принимает параметры поиска и возвращает найденные объявления.
"""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, HttpUrl
from loguru import logger

from src.parser_cls import AvitoParse
from src.dto import AvitoConfig
from src.models import ItemsResponse


# Загрузка переменных окружения
from dotenv import load_dotenv
load_dotenv()

app = FastAPI(
    title="Авито Парсер API",
    description="API для парсинга объявлений с Авито",
    version="1.0.0"
)

# Настройка аутентификации
security = HTTPBearer()

# Токен из переменных окружения
API_TOKEN = os.getenv("API_TOKEN")

logger.add("logs/api.log", rotation="5 MB", retention="5 days", level="INFO")


class ParseRequest(BaseModel):
    """Модель запроса для парсинга"""
    urls: List[HttpUrl]  # Обязательный параметр - список URL для парсинга
    min_price: Optional[int] = None  # Минимальная цена (необязательный)
    max_price: Optional[int] = None  # Максимальная цена (необязательный)  


class AdResult(BaseModel):
    """Модель объявления в результате"""
    id: int  # ID объявления
    price: int  # Цена объявления


class ParseResponse(BaseModel):
    """Модель ответа парсинга"""
    success: bool  # Успешность операции
    message: str  # Сообщение о результате
    ads: List[AdResult]  # Найденные объявления
    total_found: int  # Общее количество найденных объявлений


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена аутентификации"""
    if credentials.credentials != API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен аутентификации",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работоспособности API"""
    return {"message": "Авито Парсер API работает", "status": "ok"}


@app.post("/parse", response_model=ParseResponse)
async def parse_avito(
    request: ParseRequest,
    token: str = Depends(verify_token)
):
    """
    Парсинг объявлений с Авито
    
    Принимает параметры поиска и возвращает найденные объявления с ID и ценой.
    Требует аутентификации по токену в заголовке Authorization: Bearer <token>
    
    Args:
        request: Параметры запроса (urls, min_price, max_price)
        token: Токен аутентификации (автоматически извлекается из заголовка)
        
    Returns:
        ParseResponse: Результат парсинга с найденными объявлениями
        
    Raises:
        HTTPException: 401 при неверном токене, 500 при ошибке парсинга
    """
    try:
        logger.info(f"Начат парсинг для {len(request.urls)} URL(s)")
        
        # Загружаем список ссылок для смены IP из переменной окружения
        # Формат: "url1|url2|url3"
        proxy_change_urls_str = os.getenv("PROXY_CHANGE_URLS", "")
        proxy_change_urls = []
        if proxy_change_urls_str:
            proxy_change_urls = [url.strip() for url in proxy_change_urls_str.split("|") if url.strip()]
        
        # Создаем конфигурацию для парсера
        config = AvitoConfig(
            urls=[str(url) for url in request.urls],
            min_price=request.min_price or 0,
            max_price=request.max_price or 999999999,
            geo="",
            count=1,  # Одна страница за запрос
            one_time_start=True,  # Однократный запуск без циклов
            pause_general=0,  # Убираем общую паузу
            pause_between_links=0,  # Убираем паузу между ссылками
            max_count_of_retry=3,
            keys_word_white_list=[],
            keys_word_black_list=[],
            seller_black_list=[],
            ignore_reserv=False,
            ignore_promotion=False,
            one_file_for_link=False,
            parse_views=False,
            max_age=0,  # Без ограничения по возрасту
            proxy_string=os.getenv("PROXY_STRING"),  # Загружаем прокси из .env
            proxy_change_url=os.getenv("PROXY_CHANGE_URL"),  # Загружаем URL смены IP из .env (fallback)
            proxy_change_urls=proxy_change_urls,  # Загружаем список ссылок для смены IP из .env
        )
        
        # Создаем экземпляр парсера (без БД/антидубликатов)
        parser = AvitoParse(config=config)
        
        # Выполняем парсинг
        found_ads = []
        
        # Модифицированная логика парсинга для API
        parser.load_cookies()
        
        for url in config.urls:
            logger.info(f"Парсинг URL: {url}")
            
            # Получаем HTML страницы
            html_code = parser.fetch_data(url=url, retries=config.max_count_of_retry)
            
            if not html_code:
                logger.warning(f"Не удалось получить данные для URL: {url}")
                continue
                
            # Извлекаем данные со страницы
            data_from_page = parser.find_json_on_page(html_code=html_code)
            
            if not data_from_page:
                logger.warning(f"Не найдены данные объявлений на странице: {url}")
                continue
                
            try:
                ads_models = ItemsResponse(**data_from_page.get("data", {}).get("catalog", {}))
            except Exception as err:
                logger.error(f"Ошибка валидации объявлений: {err}")
                continue
                
            # Очищаем и фильтруем объявления
            ads = parser._clean_null_ads(ads=ads_models.items)
            ads = parser._add_seller_to_ads(ads=ads)
            
            # Применяем фильтры
            filtered_ads = parser.filter_ads(ads=ads)
            
            # Добавляем в результат только ID и цену
            for ad in filtered_ads:
                if ad.id and ad.priceDetailed and ad.priceDetailed.value:
                    found_ads.append(AdResult(
                        id=ad.id if isinstance(ad.id, int) else ad.id.get('value', 0) if isinstance(ad.id, dict) else 0,
                        price=ad.priceDetailed.value
                    ))
        
        logger.info(f"Найдено {len(found_ads)} объявлений")
        
        return ParseResponse(
            success=True,
            message=f"Успешно найдено {len(found_ads)} объявлений",
            ads=found_ads,
            total_found=len(found_ads)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при выполнении парсинга: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {"status": "healthy", "service": "avito-parser-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=5000, 
        log_level="info"
    )
