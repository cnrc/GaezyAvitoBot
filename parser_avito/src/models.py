"""
Модели данных для парсера Avito

Данный файл содержит Pydantic модели для структурирования и валидации данных,
получаемых при парсинге объявлений с сайта Avito.ru. Модели описывают схему
данных для различных компонентов объявлений: категории, локации, цены, 
изображения, контакты и другие элементы.

Основная модель Item представляет полную структуру объявления со всеми
возможными полями и вложенными объектами.
"""

from pydantic import BaseModel, HttpUrl, RootModel
from typing import List, Optional, Dict, Any


class Category(BaseModel):
    """Модель категории объявления на Avito"""
    id: int              # Уникальный идентификатор категории
    name: str            # Название категории
    slug: str            # Слаг категории для URL
    rootId: int          # ID родительской категории
    compare: bool        # Возможность сравнения товаров в категории
    pageRootId: int | None  # ID корневой страницы категории


class Location(BaseModel):
    """Модель локации/местоположения объявления"""
    id: int                      # Уникальный идентификатор локации
    name: str                    # Название локации (город, регион)
    namePrepositional: str       # Название в предложном падеже
    isCurrent: bool              # Является ли текущей локацией пользователя
    isRegion: bool               # Является ли регионом (не городом)


class AddressDetailed(BaseModel):
    """Детализированная информация об адресе"""
    locationName: str            # Название локации в адресе


class PriceDetailed(BaseModel):
    """Детализированная информация о цене товара/услуги"""
    enabled: bool                         # Включено ли отображение цены
    fullString: str                       # Полная строка цены
    hasValue: bool                        # Есть ли числовое значение цены
    postfix: str                         # Постфикс цены (рублей, за кг и т.д.)
    string: str                          # Строковое представление цены
    stringWithoutDiscount: Optional[str] # Цена без учета скидки
    title: Dict[str, str]                # Заголовки цены в разных падежах
    titleDative: str                     # Заголовок в дательном падеже
    value: int                           # Числовое значение цены
    wasLowered: bool                     # Была ли цена понижена
    exponent: str                        # Степень (множитель цены)


class Image(RootModel):
    """Модель изображения с различными размерами"""
    root: Dict[str, HttpUrl]     # Словарь с URL изображений разных размеров


class Geo(BaseModel):
    """Геолокационная информация объявления"""
    geoReferences: List[Any]     # Список геореференсов
    formattedAddress: str        # Форматированный адрес


class Contacts(BaseModel):
    """Контактная информация продавца"""
    phone: bool                       # Доступен ли телефон
    delivery: bool                    # Доступна ли доставка
    message: bool                     # Можно ли отправить сообщение
    messageTitle: str                 # Заголовок для сообщений
    action: str                       # Действие при контакте
    onModeration: bool               # На модерации ли контакты
    hasCVPackage: bool               # Есть ли пакет резюме
    hasEmployeeBalanceForCv: bool    # Есть ли баланс сотрудника для резюме
    serviceBooking: bool             # Доступно ли бронирование услуг


class Gallery(BaseModel):
    """Галерея изображений объявления"""
    alt: str | None = None               # Альтернативный текст для изображения
    cropImagesInfo: Optional[Any]        # Информация об обрезке изображений
    extraPhoto: Optional[Any]            # Дополнительные фотографии
    hasLeadgenOverlay: bool              # Есть ли оверлей для лидгена
    has_big_image: bool                  # Есть ли большое изображение
    imageAlt: str                        # Альтернативный текст изображения
    imageLargeUrl: str                   # URL большого изображения
    imageLargeVipUrl: str                # URL большого VIP изображения
    imageUrl: str                        # URL обычного изображения
    imageVipUrl: str                     # URL VIP изображения
    image_large_urls: List[Any]          # Список URL больших изображений
    image_urls: List[Any]                # Список URL всех изображений
    images: List[Any]                    # Массив объектов изображений
    imagesCount: int                     # Количество изображений
    isFirstImageHighImportance: bool     # Является ли первое изображение важным
    isLazy: bool                         # Используется ли ленивая загрузка
    noPhoto: bool                        # Отсутствуют ли фотографии
    showSlider: bool                     # Показывать ли слайдер
    wideSnippetUrls: List[Any]           # URL для широких сниппетов


class UserLogo(BaseModel):
    """Логотип пользователя/продавца"""
    link: str | None = None               # Ссылка на профиль пользователя
    src: HttpUrl | str | None = None      # URL логотипа
    developerId: Optional[int]           # ID разработчика


class IvaComponent(BaseModel):
    """Компонент системы IVA (интерактивный голосовой помощник)"""
    component: str                        # Название компонента
    payload: Optional[Dict[str, Any]] = None  # Дополнительные данные компонента


class IvaStep(BaseModel):
    """Шаг в системе IVA"""
    componentData: IvaComponent           # Данные компонента
    payload: Optional[Dict[str, Any]] = None  # Полезная нагрузка шага
    default: bool                         # Является ли шаг по умолчанию


class Item(BaseModel):
    """
    Основная модель объявления на Avito
    
    Содержит всю информацию о товаре или услуге: 
    заголовок, описание, цена, категория, фотографии,
    местоположение, контактная информация и другие данные.
    Ли поля опциональны, так как не все данные могут быть
    доступны для каждого объявления.
    """
    id: int | dict | None = None
    categoryId: int | dict | None = None
    locationId: int | dict | None = None
    isVerifiedItem: bool | None = None
    urlPath: str | None = None
    title: str | None = None
    description: str | None = None
    category: Category | None = None
    location: Location | None = None
    addressDetailed: AddressDetailed | None = None
    sortTimeStamp: int | None = None
    turnOffDate: bool | None = None
    priceDetailed: PriceDetailed | None = None
    normalizedPrice: Optional[str] | None = None
    priceWithoutDiscount: Optional[str] | None = None
    discountPercent: Optional[int] | Optional[str] | None = None
    lastMinuteOffer: Optional[str] | Optional[dict] | None = None
    images: List[Image] | None = None
    imagesCount: int | None = None
    isFavorite: bool | None = None
    isNew: bool | None = None
    geo: Geo | None = None
    phoneImage: Optional[str] | None = None
    cvViewed: bool | None = None
    isXl: bool | None = None
    hasFooter: bool | None = None
    contacts: Contacts | None = None
    gallery: Gallery | None = None
    loginLink: str | None = None
    authLink: str | None = None
    userLogo: UserLogo | None = None
    isMarketplace: bool | None = None
    iva: Dict[str, List[IvaStep]] | None = None
    hasVideo: bool | None = None
    hasRealtyLayout: bool | None = None
    coords: Dict[str, Any] | None = None
    groupData: Optional[Any] | None = None
    isReMapPromotion: bool | None = None
    isReserved: bool | None = None
    type: str | None = None
    ratingExperimentGroup: str | None = None
    isRatingExperiment: bool | None = None
    closedItemsText: str | None = None
    closestAddressId: int | None = None
    isSparePartsCompatibility: bool | None = None
    sellerId: str | None = None
    isPromotion: bool = False
    total_views: int | None = None
    today_views: int | None = None


class ItemsResponse(BaseModel):
    """Ответ API со списком объявлений"""
    items: List[Item]  # Список объявлений
