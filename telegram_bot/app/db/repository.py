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
    Promocode, PromoUsage, Tracked, AsyncSessionLocal
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


# =================== ОТСЛЕЖИВАНИЯ ===================

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


# =================== СТАТИСТИКА ===================

async def get_monthly_statistics() -> dict:
    """Получает статистику за последний месяц."""
    try:
        async with AsyncSessionLocal() as session:
            from datetime import datetime, timedelta
            from sqlalchemy import func, and_
            
            # Дата месяц назад
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            # 1. Новые пользователи за месяц
            new_users_result = await session.execute(
                select(func.count(User.id))
                .where(User.created_at >= month_ago)
            )
            new_users_count = new_users_result.scalar() or 0
            
            # 2. Пользователи с активной подпиской
            active_subscriptions_result = await session.execute(
                select(func.count(UserSubscription.id.distinct()))
                .where(UserSubscription.end_date > datetime.utcnow())
            )
            active_subscriptions_count = active_subscriptions_result.scalar() or 0
            
            # 3. Сумма всех успешных платежей за месяц
            payments_sum_result = await session.execute(
                select(func.coalesce(func.sum(SubscriptionPlan.price), 0))
                .join(Payment, Payment.plan_id == SubscriptionPlan.id)
                .where(and_(Payment.created_at >= month_ago, Payment.status == True))
            )
            total_revenue = float(payments_sum_result.scalar() or 0)
            
            # 4. Общее количество пользователей
            total_users_result = await session.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar() or 0
            
            # 5. Активные отслеживания
            active_trackings_result = await session.execute(
                select(func.count(Tracked.id))
                .where(Tracked.is_active == True)
            )
            active_trackings = active_trackings_result.scalar() or 0
            
            # 6. Использованные промокоды за месяц
            used_promos_result = await session.execute(
                select(func.count(PromoUsage.id))
                .where(PromoUsage.used_at >= month_ago)
            )
            used_promos = used_promos_result.scalar() or 0
            
            # 7. Успешные платежи за месяц
            successful_payments_result = await session.execute(
                select(func.count(Payment.id))
                .where(and_(Payment.created_at >= month_ago, Payment.status == True))
            )
            successful_payments = successful_payments_result.scalar() or 0
            
            return {
                'period_days': 30,
                'new_users_month': new_users_count,
                'active_subscriptions': active_subscriptions_count,
                'total_revenue_month': total_revenue,
                'total_users': total_users,
                'active_trackings': active_trackings,
                'used_promos_month': used_promos,
                'successful_payments_month': successful_payments,
                'generated_at': datetime.utcnow()
            }
            
    except Exception as e:
        print(f"❌ Ошибка при получении статистики: {e}")
        import traceback
        traceback.print_exc()
        return {}


async def get_popular_subscription_plans() -> list:
    """Получает самые популярные планы подписок за последний месяц."""
    try:
        async with AsyncSessionLocal() as session:
            from datetime import datetime, timedelta
            from sqlalchemy import func
            
            month_ago = datetime.utcnow() - timedelta(days=30)
            
            result = await session.execute(
                select(
                    SubscriptionPlan.name,
                    SubscriptionPlan.price,
                    func.count(Payment.id).label('purchases_count')
                )
                .join(Payment, Payment.plan_id == SubscriptionPlan.id)
                .where(Payment.created_at >= month_ago)
                .where(Payment.status == True)
                .group_by(SubscriptionPlan.id, SubscriptionPlan.name, SubscriptionPlan.price)
                .order_by(func.count(Payment.id).desc())
            )
            
            plans = []
            for row in result:
                plans.append({
                    'name': row.name,
                    'price': float(row.price),
                    'purchases': row.purchases_count
                })
            
            return plans
            
    except Exception as e:
        print(f"❌ Ошибка при получении популярных планов: {e}")
        import traceback
        traceback.print_exc()
        return []


async def get_daily_activity_stats(days: int = 7) -> list:
    """Получает статистику активности по дням."""
    try:
        async with AsyncSessionLocal() as session:
            from datetime import datetime, timedelta
            from sqlalchemy import func, cast, Date
            
            stats = []
            for i in range(days):
                date = datetime.utcnow().date() - timedelta(days=i)
                next_date = date + timedelta(days=1)
                
                # Новые пользователи в этот день
                new_users_result = await session.execute(
                    select(func.count(User.id))
                    .where(cast(User.created_at, Date) == date)
                )
                new_users = new_users_result.scalar() or 0
                
                # Успешные платежи в этот день
                payments_result = await session.execute(
                    select(func.count(Payment.id))
                    .where(cast(Payment.created_at, Date) == date)
                    .where(Payment.status == True)
                )
                payments = payments_result.scalar() or 0
                
                stats.append({
                    'date': date.strftime('%d.%m.%Y'),
                    'new_users': new_users,
                    'successful_payments': payments
                })
            
            return list(reversed(stats))  # От старых к новым
            
    except Exception as e:
        print(f"❌ Ошибка при получении дневной статистики: {e}")
        import traceback
        traceback.print_exc()
        return []


# =================== УВЕДОМЛЕНИЯ ===================

async def get_all_users() -> list:
    """Получает всех пользователей для рассылки уведомлений."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            return [{'telegram_id': user.telegram_id, 'is_admin': user.is_admin} for user in users]
    except Exception as e:
        print(f"❌ Ошибка при получении всех пользователей: {e}")
        import traceback
        traceback.print_exc()
        return []


async def get_users_with_active_subscription() -> list:
    """Получает пользователей с активной подпиской."""
    try:
        async with AsyncSessionLocal() as session:
            from datetime import datetime
            
            result = await session.execute(
                select(User)
                .join(UserSubscription, User.id == UserSubscription.user_id)
                .where(UserSubscription.end_date > datetime.utcnow())
                .distinct()
            )
            users = result.scalars().all()
            return [{'telegram_id': user.telegram_id, 'is_admin': user.is_admin} for user in users]
    except Exception as e:
        print(f"❌ Ошибка при получении пользователей с подпиской: {e}")
        import traceback
        traceback.print_exc()
        return []


async def get_users_without_active_subscription() -> list:
    """Получает пользователей без активной подписки."""
    try:
        async with AsyncSessionLocal() as session:
            from datetime import datetime
            from sqlalchemy import and_, not_, exists
            
            # Подзапрос для проверки наличия активной подписки
            active_subscription_subquery = (
                select(UserSubscription.user_id)
                .where(UserSubscription.end_date > datetime.utcnow())
            )
            
            result = await session.execute(
                select(User)
                .where(not_(User.id.in_(active_subscription_subquery)))
            )
            users = result.scalars().all()
            return [{'telegram_id': user.telegram_id, 'is_admin': user.is_admin} for user in users]
    except Exception as e:
        print(f"❌ Ошибка при получении пользователей без подписки: {e}")
        import traceback
        traceback.print_exc()
        return []


async def get_notification_stats() -> dict:
    """Получает статистику для уведомлений."""
    try:
        async with AsyncSessionLocal() as session:
            from datetime import datetime
            from sqlalchemy import func
            
            # Всего пользователей
            total_users_result = await session.execute(select(func.count(User.id)))
            total_users = total_users_result.scalar() or 0
            
            # С активной подпиской
            active_sub_result = await session.execute(
                select(func.count(UserSubscription.user_id.distinct()))
                .where(UserSubscription.end_date > datetime.utcnow())
            )
            with_subscription = active_sub_result.scalar() or 0
            
            # Без активной подписки
            without_subscription = total_users - with_subscription
            
            return {
                'total_users': total_users,
                'with_subscription': with_subscription,
                'without_subscription': without_subscription
            }
    except Exception as e:
        print(f"❌ Ошибка при получении статистики уведомлений: {e}")
        import traceback
        traceback.print_exc()
        return {'total_users': 0, 'with_subscription': 0, 'without_subscription': 0}


