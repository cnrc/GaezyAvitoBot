"""
Middlewares для телеграм бота
"""
from .subscription_check import SubscriptionCheckMiddleware

__all__ = ['SubscriptionCheckMiddleware']
