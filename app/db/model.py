import asyncio
from sqlalchemy import create_engine, Column, Text, Integer, Boolean, DateTime, Numeric, ForeignKey, CheckConstraint, text
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime
from ..config import DATABASE_URL

Base = declarative_base()

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
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init_models())
    print("Таблицы успешно созданы!")