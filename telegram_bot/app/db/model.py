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
    active_promocode = relationship("UserActivePromocode", back_populates="user", uselist=False, cascade="all, delete-orphan")
    trackings = relationship("Tracked", back_populates="user", cascade="all, delete-orphan")

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


class Tracked(Base):
    """Таблица отслеживаемых объявлений пользователя"""
    __tablename__ = 'tracked'
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(Text, nullable=True)
    link = Column(Text, nullable=False)
    min_price = Column(Integer, nullable=True)
    max_price = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="trackings")



async def init_models():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Эти функции перенесены в repository.py для лучшей организации кода

# Функции для работы с пользователями, подписками и промокодами перенесены в repository.py


# Функции для работы с отслеживаниями

async def add_tracking(telegram_id: str, link: str, name: str = None, min_price: int = None, max_price: int = None) -> bool:
    """Добавляет новое отслеживание для пользователя."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print(f"❌ Пользователь {telegram_id} не найден")
                return False
            
            # Создаем новое отслеживание
            tracking = Tracked(
                user_id=user.id,
                name=name,
                link=link,
                min_price=min_price,
                max_price=max_price,
                is_active=True
            )
            session.add(tracking)
            await session.commit()
            
            print(f"✅ Добавлено отслеживание для пользователя {telegram_id}: {link}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при добавлении отслеживания: {e}")
        import traceback
        traceback.print_exc()
        return False


async def get_user_trackings(telegram_id: str, active_only: bool = True) -> list:
    """Получает список отслеживаний пользователя."""
    try:
        async with AsyncSessionLocal() as session:
            query = select(Tracked).join(User, User.id == Tracked.user_id).where(User.telegram_id == telegram_id)
            
            if active_only:
                query = query.where(Tracked.is_active == True)
            
            result = await session.execute(query)
            trackings = result.scalars().all()
            
            return trackings
            
    except Exception as e:
        print(f"❌ Ошибка при получении отслеживаний: {e}")
        import traceback
        traceback.print_exc()
        return []


async def archive_tracking(telegram_id: str, tracking_id: str) -> bool:
    """Архивирует отслеживание (устанавливает is_active = False)."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем отслеживание пользователя
            result = await session.execute(
                select(Tracked).join(User, User.id == Tracked.user_id)
                .where(User.telegram_id == telegram_id)
                .where(Tracked.id == tracking_id)
            )
            tracking = result.scalar_one_or_none()
            
            if not tracking:
                print(f"❌ Отслеживание {tracking_id} не найдено для пользователя {telegram_id}")
                return False
            
            tracking.is_active = False
            tracking.updated_at = datetime.utcnow()
            await session.commit()
            
            print(f"✅ Отслеживание {tracking_id} заархивировано для пользователя {telegram_id}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при архивировании отслеживания: {e}")
        import traceback
        traceback.print_exc()
        return False


async def archive_all_user_trackings(telegram_id: str) -> int:
    """Архивирует все активные отслеживания пользователя. Возвращает количество заархивированных."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем все активные отслеживания пользователя
            result = await session.execute(
                select(Tracked).join(User, User.id == Tracked.user_id)
                .where(User.telegram_id == telegram_id)
                .where(Tracked.is_active == True)
            )
            active_trackings = result.scalars().all()
            
            if not active_trackings:
                return 0
            
            # Архивируем все активные отслеживания
            archived_count = 0
            for tracking in active_trackings:
                tracking.is_active = False
                tracking.updated_at = datetime.utcnow()
                archived_count += 1
            
            await session.commit()
            
            print(f"✅ Заархивировано {archived_count} отслеживаний для пользователя {telegram_id}")
            return archived_count
            
    except Exception as e:
        print(f"❌ Ошибка при архивировании всех отслеживаний: {e}")
        import traceback
        traceback.print_exc()
        return 0


async def restore_tracking(telegram_id: str, tracking_id: str) -> bool:
    """Восстанавливает отслеживание (устанавливает is_active = True)."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем отслеживание пользователя
            result = await session.execute(
                select(Tracked).join(User, User.id == Tracked.user_id)
                .where(User.telegram_id == telegram_id)
                .where(Tracked.id == tracking_id)
            )
            tracking = result.scalar_one_or_none()
            
            if not tracking:
                print(f"❌ Отслеживание {tracking_id} не найдено для пользователя {telegram_id}")
                return False
            
            tracking.is_active = True
            tracking.updated_at = datetime.utcnow()
            await session.commit()
            
            print(f"✅ Отслеживание {tracking_id} восстановлено для пользователя {telegram_id}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при восстановлении отслеживания: {e}")
        import traceback
        traceback.print_exc()
        return False


async def delete_tracking(telegram_id: str, tracking_id: str) -> bool:
    """Удаляет отслеживание пользователя."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем отслеживание пользователя
            result = await session.execute(
                select(Tracked).join(User, User.id == Tracked.user_id)
                .where(User.telegram_id == telegram_id)
                .where(Tracked.id == tracking_id)
            )
            tracking = result.scalar_one_or_none()
            
            if not tracking:
                print(f"❌ Отслеживание {tracking_id} не найдено для пользователя {telegram_id}")
                return False
            
            await session.delete(tracking)
            await session.commit()
            
            print(f"✅ Отслеживание {tracking_id} удалено для пользователя {telegram_id}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при удалении отслеживания: {e}")
        import traceback
        traceback.print_exc()
        return False


async def get_all_active_tracked_items() -> list:
    """Получает все активные отслеживания для проверки планировщиком."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tracked).where(Tracked.is_active == True)
            )
            trackings = result.scalars().all()
            return trackings
            
    except Exception as e:
        print(f"❌ Ошибка при получении всех активных отслеживаний: {e}")
        import traceback
        traceback.print_exc()
        return []


async def update_tracked_item_state(tracking: Tracked, price: float = None, title: str = None, description: str = None) -> bool:
    """Обновляет состояние отслеживаемого объявления."""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем отслеживание по ID для обновления
            result = await session.execute(
                select(Tracked).where(Tracked.id == tracking.id)
            )
            tracked_item = result.scalar_one_or_none()
            
            if not tracked_item:
                print(f"❌ Отслеживание {tracking.id} не найдено для обновления")
                return False
            
            # Обновляем поля (пока у нас простая модель, расширим при необходимости)
            tracked_item.updated_at = datetime.utcnow()
            
            # TODO: При необходимости можно добавить поля last_price, last_title, last_description в модель
            
            await session.commit()
            
            print(f"✅ Состояние отслеживания {tracking.id} обновлено")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении состояния отслеживания: {e}")
        import traceback
        traceback.print_exc()
        return False