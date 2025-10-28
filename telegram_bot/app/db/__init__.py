"""
Экспорт основных моделей и функций для работы с БД
"""
from .model import (
    Base,
    User,
    SubscriptionPlan,
    UserSubscription,
    Payment,
    Promocode,
    PromoUsage,
    UserActivePromocode,
    Tracked,
    AsyncSessionLocal,
    init_models
)

from .repository import (
    # Пользователи
    get_or_create_user,
    
    # Подписки
    user_has_active_subscription,
    user_has_ever_had_subscription,
    create_trial_subscription,
    
    # Промокоды
    user_has_used_promocode,
    get_user_active_promocode,
    set_user_active_promocode,
    get_user_current_promocode,
    clear_user_promocode,
    
    # Функции отслеживания
    add_tracking,
    get_user_trackings,
    archive_tracking,
    archive_all_user_trackings,
    restore_tracking,
    delete_tracking,
    get_all_active_tracked_items,
    update_tracked_item_state,
    
    # Функции статистики
    get_monthly_statistics,
    get_popular_subscription_plans,
    get_daily_activity_stats
)

__all__ = [
    # Модели
    'Base',
    'User',
    'SubscriptionPlan',
    'UserSubscription',
    'Payment',
    'Promocode',
    'PromoUsage',
    'UserActivePromocode',
    'Tracked',
    'AsyncSessionLocal',
    'init_models',
    
    # Функции пользователей
    'get_or_create_user',
    'user_has_active_subscription',
    'user_has_ever_had_subscription',
    'create_trial_subscription',
    
    # Функции промокодов
    'user_has_used_promocode',
    'get_user_active_promocode',
    'set_user_active_promocode',
    'get_user_current_promocode',
    'clear_user_promocode',
    
    # Функции отслеживания
    'add_tracking',
    'get_user_trackings',
    'archive_tracking',
    'archive_all_user_trackings',
    'restore_tracking',
    'delete_tracking',
    'get_all_active_tracked_items',
    'update_tracked_item_state',
    
    # Функции статистики
    'get_monthly_statistics',
    'get_popular_subscription_plans',
    'get_daily_activity_stats'
]
