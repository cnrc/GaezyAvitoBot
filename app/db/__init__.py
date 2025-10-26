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
    TrackedItem,
    TrackedSearch,
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
    
    # Отслеживание объявлений
    add_tracked_item,
    remove_tracked_item,
    get_user_tracked_items,
    get_all_active_tracked_items,
    update_tracked_item_state,
    
    # Отслеживание поисков
    add_tracked_search,
    get_user_tracked_searches,
    get_all_active_tracked_searches,
    remove_tracked_search,
    update_tracked_search_state,
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
    'TrackedItem',
    'TrackedSearch',
    'AsyncSessionLocal',
    'init_models',
    
    # Функции
    'get_or_create_user',
    'user_has_active_subscription',
    'user_has_ever_had_subscription',
    'create_trial_subscription',
    'user_has_used_promocode',
    'get_user_active_promocode',
    'set_user_active_promocode',
    'get_user_current_promocode',
    'clear_user_promocode',
    'add_tracked_item',
    'remove_tracked_item',
    'get_user_tracked_items',
    'get_all_active_tracked_items',
    'update_tracked_item_state',
    'add_tracked_search',
    'get_user_tracked_searches',
    'get_all_active_tracked_searches',
    'remove_tracked_search',
    'update_tracked_search_state',
]
