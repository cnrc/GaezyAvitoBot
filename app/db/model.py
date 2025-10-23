import asyncio
from sqlalchemy import create_engine, Column, Text, Integer, Boolean, DateTime, Numeric, ForeignKey, CheckConstraint, text, select
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime
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
    used_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="promo_usages")
    promocode = relationship("Promocode", back_populates="promo_usages")

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