import asyncio
from sqlalchemy import create_engine, Column, Text, Integer, Boolean, DateTime, Numeric, ForeignKey, CheckConstraint, text, select
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime, timedelta
from app.config import DATABASE_URL

Base = declarative_base()
async_engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    telegram_id = Column(Text, unique=True, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    promo_usages = relationship("PromoUsage", back_populates="user")
    tracked_items = relationship("TrackedItem", back_populates="user", cascade="all, delete-orphan")
    tracked_searches = relationship("TrackedSearch", back_populates="user", cascade="all, delete-orphan")
    active_promocode = relationship("UserActivePromocode", back_populates="user", uselist=False, cascade="all, delete-orphan")

class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plans'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    name = Column(Text, nullable=False)
    alias = Column(Text, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    duration_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="plan")
    payments = relationship("Payment", back_populates="plan")

class UserSubscription(Base):
    __tablename__ = 'user_subscriptions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('subscription_plans.id'), nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    plan_id = Column(UUID(as_uuid=True), ForeignKey('subscription_plans.id'), nullable=False)
    currency = Column(Text, default='RUB')
    provider = Column(Text, nullable=False)
    status = Column(Boolean, default=False)
    transaction_id = Column(Text, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    plan = relationship("SubscriptionPlan", back_populates="payments")
    promo_usages = relationship("PromoUsage", back_populates="payment")

class Promocode(Base):
    __tablename__ = 'promocodes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    code = Column(Text, unique=True, nullable=False)
    discount_percent = Column(Integer, nullable=False)
    usage_limit = Column(Integer, nullable=False)
    used_count = Column(Integer, default=0)
    expired_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    promo_usages = relationship("PromoUsage", back_populates="promocode")
    
    # Check constraint
    table_args = (
        CheckConstraint('discount_percent >= 0 AND discount_percent <= 100', 
                       name='check_discount_percent_range'),
    )

class PromoUsage(Base):
    __tablename__ = 'promo_usage'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    promo_id = Column(UUID(as_uuid=True), ForeignKey('promocodes.id'), nullable=False)
    payment_id = Column(UUID(as_uuid=True), ForeignKey('payments.id'), nullable=True)
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="promo_usages")
    promocode = relationship("Promocode", back_populates="promo_usages")
    payment = relationship("Payment", back_populates="promo_usages")


class UserActivePromocode(Base):
    """Активный промокод пользователя (для применения при следующей покупке)"""
    __tablename__ = 'user_active_promocodes'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    promo_id = Column(UUID(as_uuid=True), ForeignKey('promocodes.id', ondelete='CASCADE'), nullable=False)
    activated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="active_promocode")
    promocode = relationship("Promocode")


class TrackedItem(Base):
    """Отслеживание конкретных объявлений по ID"""
    __tablename__ = 'tracked_items'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # ID объявления на Авито
    item_id = Column(Text, nullable=False)
    
    # Последнее состояние объявления
    last_price = Column(Numeric(10, 2), nullable=True)
    last_title = Column(Text, nullable=True)
    last_description = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="tracked_items")


class TrackedSearch(Base):
    """Отслеживание новых объявлений по фильтрам"""
    __tablename__ = 'tracked_searches'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Параметры поиска
    search_query = Column(Text, nullable=True)
    category_id = Column(Integer, nullable=True)
    location_id = Column(Integer, nullable=True)
    price_from = Column(Integer, nullable=True)
    price_to = Column(Integer, nullable=True)
    
    # Состояние поиска (храним последние найденные ID в виде JSON)
    last_found_item_ids = Column(JSONB, default=list)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="tracked_searches")


async def init_models():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

# Глобальное хранилище активных промокодов пользователей (временное решение)
user_active_promocodes = {}

async def set_user_active_promocode(telegram_id: str, promocode: Promocode):
    """Устанавливает активный промокод для пользователя."""
    user_active_promocodes[telegram_id] = promocode

async def get_user_current_promocode(telegram_id: str) -> Promocode:
    """Получает текущий активный промокод пользователя (из временного хранилища)."""
    return user_active_promocodes.get(telegram_id)

async def clear_user_promocode(telegram_id: str):
    """Очищает активный промокод пользователя."""
    user_active_promocodes.pop(telegram_id, None)

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