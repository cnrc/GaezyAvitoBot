"""
Функции для работы с базой данных
Вся бизнес-логика взаимодействия с БД находится здесь
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional
from .model import (
    User, SubscriptionPlan, UserSubscription, Payment, 
    Promocode, PromoUsage, TrackedItem, TrackedSearch,
    AsyncSessionLocal
)


# =================== ПОЛЬЗОВАТЕЛИ ===================

async def get_or_create_user(telegram_id: str) -> User:
    """Создаёт пользователя при первом запуске бота или возвращает существующего."""
    print(f"🔍 DB: get_or_create_user вызвана для telegram_id: {telegram_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            print(f"🔍 DB: Выполняем запрос для поиска пользователя {telegram_id}")
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if user is None:
                print(f"🔍 DB: Пользователь {telegram_id} не найден, создаем нового")
                user = User(telegram_id=telegram_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                print(f"🔍 DB: Пользователь {telegram_id} создан успешно")
            else:
                print(f"🔍 DB: Пользователь {telegram_id} найден")
            
            return user
    except Exception as e:
        print(f"❌ DB ERROR: Ошибка в get_or_create_user: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


# =================== ПОДПИСКИ ===================

async def user_has_active_subscription(telegram_id: str) -> bool:
    """Проверяет, есть ли у пользователя активная подписка (end_date > now)."""
    print(f"🔍 DB: user_has_active_subscription вызвана для telegram_id: {telegram_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            print(f"🔍 DB: Выполняем запрос для проверки подписки {telegram_id}")
            result = await session.execute(
                select(UserSubscription)
                .join(User, User.id == UserSubscription.user_id)
                .where(User.telegram_id == telegram_id)
                .where(UserSubscription.end_date > datetime.utcnow())
            )
            has_subscription = result.first() is not None
            print(f"🔍 DB: Пользователь {telegram_id} имеет активную подписку: {has_subscription}")
            return has_subscription
    except Exception as e:
        print(f"❌ DB ERROR: Ошибка в user_has_active_subscription: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def user_has_ever_had_subscription(telegram_id: str) -> bool:
    """Проверяет, была ли у пользователя когда-либо подписка."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserSubscription)
            .join(User, User.id == UserSubscription.user_id)
            .where(User.telegram_id == telegram_id)
        )
        return result.first() is not None


async def create_trial_subscription(telegram_id: str) -> bool:
    """Создает trial подписку на 3 дня для нового пользователя."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print(f"❌ Пользователь {telegram_id} не найден для создания trial подписки")
                return False
            
            # Получаем самый дешевый план для создания trial подписки
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
            )
            plans = result.scalars().all()
            
            if not plans:
                print(f"❌ Нет доступных планов для создания trial подписки")
                return False
            
            # Берем самый дешевый план
            cheapest_plan = min(plans, key=lambda p: float(p.price))
            
            # Создаем trial подписку на 3 дня
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=3)
            
            subscription = UserSubscription(
                user_id=user.id,
                plan_id=cheapest_plan.id,
                start_date=start_date,
                end_date=end_date
            )
            session.add(subscription)
            await session.commit()
            
            print(f"✅ Trial подписка создана для пользователя {telegram_id} до {end_date}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при создании trial подписки: {e}")
        import traceback
        traceback.print_exc()
        return False


# =================== ПРОМОКОДЫ ===================

# Глобальное хранилище активных промокодов пользователей (временное решение)
user_active_promocodes = {}


async def user_has_used_promocode(telegram_id: str) -> bool:
    """Проверяет, использовал ли пользователь когда-либо промокод."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PromoUsage)
            .join(User, User.id == PromoUsage.user_id)
            .where(User.telegram_id == telegram_id)
        )
        return result.first() is not None


async def get_user_active_promocode(telegram_id: str) -> Promocode:
    """Получает активный промокод пользователя (если есть)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Promocode)
            .join(PromoUsage, PromoUsage.promo_id == Promocode.id)
            .join(User, User.id == PromoUsage.user_id)
            .where(User.telegram_id == telegram_id)
            .where(Promocode.expired_at > datetime.utcnow())
        )
        return result.scalar_one_or_none()


async def set_user_active_promocode(telegram_id: str, promocode: Promocode):
    """Устанавливает активный промокод для пользователя в БД."""
    from .model import UserActivePromocode
    
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        # Проверяем, есть ли уже активный промокод
        existing = await session.execute(
            select(UserActivePromocode).where(UserActivePromocode.user_id == user.id)
        )
        existing_promo = existing.scalar_one_or_none()
        
        if existing_promo:
            # Обновляем существующий
            existing_promo.promo_id = promocode.id
            existing_promo.activated_at = datetime.utcnow()
        else:
            # Создаем новый
            active_promo = UserActivePromocode(
                user_id=user.id,
                promo_id=promocode.id
            )
            session.add(active_promo)
        
        await session.commit()


async def get_user_current_promocode(telegram_id: str) -> Optional[Promocode]:
    """Получает текущий активный промокод пользователя из БД."""
    from .model import UserActivePromocode
    
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Получаем активный промокод пользователя
        result = await session.execute(
            select(UserActivePromocode).where(UserActivePromocode.user_id == user.id)
        )
        active_promo = result.scalar_one_or_none()
        
        if not active_promo:
            return None
        
        # Получаем сам промокод
        promo_result = await session.execute(
            select(Promocode).where(Promocode.id == active_promo.promo_id)
        )
        return promo_result.scalar_one_or_none()


async def clear_user_promocode(telegram_id: str):
    """Очищает активный промокод пользователя."""
    from .model import UserActivePromocode
    
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return
        
        # Удаляем активный промокод
        result = await session.execute(
            select(UserActivePromocode).where(UserActivePromocode.user_id == user.id)
        )
        active_promo = result.scalar_one_or_none()
        
        if active_promo:
            await session.delete(active_promo)
            await session.commit()


# =================== ОТСЛЕЖИВАНИЕ ОБЪЯВЛЕНИЙ ===================

async def add_tracked_item(telegram_id: str, item_id: str, price: float = None, title: str = None) -> TrackedItem:
    """Добавить объявление для отслеживания по ID"""
    async with AsyncSessionLocal() as session:
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        # Проверяем, не отслеживается ли уже это объявление
        existing = await session.execute(
            select(TrackedItem)
            .where(TrackedItem.user_id == user.id)
            .where(TrackedItem.item_id == item_id)
            .where(TrackedItem.is_active == True)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Item already tracked")
        
        tracked_item = TrackedItem(
            user_id=user.id,
            item_id=item_id,
            last_price=price,
            last_title=title,
            is_active=True
        )
        session.add(tracked_item)
        await session.commit()
        await session.refresh(tracked_item)
        return tracked_item


async def remove_tracked_item(telegram_id: str, item_id: str) -> bool:
    """Удалить объявление из отслеживания (архивировать)"""
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False
        
        result = await session.execute(
            select(TrackedItem)
            .where(TrackedItem.user_id == user.id)
            .where(TrackedItem.item_id == item_id)
            .where(TrackedItem.is_active == True)
        )
        tracked_item = result.scalar_one_or_none()
        
        if not tracked_item:
            return False
        
        tracked_item.is_active = False
        await session.commit()
        return True


async def get_user_tracked_items(telegram_id: str) -> list[TrackedItem]:
    """Получить все активные отслеживаемые объявления пользователя"""
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return []
        
        result = await session.execute(
            select(TrackedItem)
            .where(TrackedItem.user_id == user.id)
            .where(TrackedItem.is_active == True)
        )
        return list(result.scalars().all())


async def get_all_active_tracked_items() -> list[TrackedItem]:
    """Получить все активные отслеживаемые объявления для проверки"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrackedItem).where(TrackedItem.is_active == True)
        )
        return list(result.scalars().all())


async def update_tracked_item_state(tracked_item: TrackedItem, price: float = None, title: str = None, description: str = None):
    """Обновить состояние отслеживаемого объявления"""
    async with AsyncSessionLocal() as session:
        tracked_item = await session.merge(tracked_item)
        if price is not None:
            tracked_item.last_price = price
        if title is not None:
            tracked_item.last_title = title
        if description is not None:
            tracked_item.last_description = description
        tracked_item.last_checked_at = datetime.utcnow()
        await session.commit()


async def add_tracked_search(telegram_id: str, search_query: str = None, category_id: int = None, 
                             location_id: int = None, price_from: int = None, price_to: int = None) -> TrackedSearch:
    """Добавить поиск для отслеживания новых объявлений"""
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")
        
        tracked_search = TrackedSearch(
            user_id=user.id,
            search_query=search_query,
            category_id=category_id,
            location_id=location_id,
            price_from=price_from,
            price_to=price_to,
            is_active=True,
            last_found_item_ids=[]
        )
        session.add(tracked_search)
        await session.commit()
        await session.refresh(tracked_search)
        return tracked_search


async def get_user_tracked_searches(telegram_id: str) -> list[TrackedSearch]:
    """Получить все активные отслеживаемые поиски пользователя"""
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return []
        
        result = await session.execute(
            select(TrackedSearch)
            .where(TrackedSearch.user_id == user.id)
            .where(TrackedSearch.is_active == True)
        )
        return list(result.scalars().all())


async def get_all_active_tracked_searches() -> list[TrackedSearch]:
    """Получить все активные отслеживаемые поиски для проверки"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TrackedSearch).where(TrackedSearch.is_active == True)
        )
        return list(result.scalars().all())


async def remove_tracked_search(telegram_id: str, search_id: str) -> bool:
    """Удалить поиск из отслеживания (архивировать)"""
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            return False
        
        result = await session.execute(
            select(TrackedSearch)
            .where(TrackedSearch.id == search_id)
            .where(TrackedSearch.user_id == user.id)
            .where(TrackedSearch.is_active == True)
        )
        tracked_search = result.scalar_one_or_none()
        
        if not tracked_search:
            return False
        
        tracked_search.is_active = False
        await session.commit()
        return True


async def update_tracked_search_state(tracked_search: TrackedSearch, found_item_ids: list[str]):
    """Обновить состояние отслеживаемого поиска"""
    async with AsyncSessionLocal() as session:
        tracked_search = await session.merge(tracked_search)
        tracked_search.last_found_item_ids = found_item_ids
        tracked_search.last_checked_at = datetime.utcnow()
        await session.commit()

