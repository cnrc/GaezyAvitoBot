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