"""
Административные функции и работа с промокодами
"""
import asyncio
import re
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, delete
from decimal import Decimal
from datetime import datetime
from ...db.model import AsyncSessionLocal, User, SubscriptionPlan, Promocode
from ...db import get_monthly_statistics, get_popular_subscription_plans, get_daily_activity_stats
from ...db import get_all_users, get_users_with_active_subscription, get_users_without_active_subscription, get_notification_stats
from .base import get_main_keyboard

router = Router()

# Простейшее состояние админских операций (без FSM)
admin_state = {}
promo_state = {}  # Состояние для ввода промокода пользователем
notification_state = {}  # Состояние для рассылки уведомлений: {admin_id: {"target": "all/active/inactive", "message": "text"}}

def clean_html_message(text: str) -> str:
    """Очищает HTML сообщение от неподдерживаемых тегов и исправляет разметку."""
    if not text:
        return text
    
    # Заменяем неподдерживаемые теги на поддерживаемые или убираем их
    replacements = {
        r'<br\s*/?>' : '\n',  # <br> -> перенос строки
        r'<br\s*/>' : '\n',   # <br/> -> перенос строки  
        r'<p\b[^>]*>' : '',   # удаляем открывающие <p>
        r'</p>' : '\n',       # </p> -> перенос строки
        r'<div\b[^>]*>' : '', # удаляем открывающие <div>
        r'</div>' : '\n',     # </div> -> перенос строки
        r'<span\b[^>]*>' : '',# удаляем открывающие <span>
        r'</span>' : '',      # удаляем закрывающие </span>
        r'<strong\b[^>]*>' : '<b>', # <strong> -> <b>
        r'</strong>' : '</b>',      # </strong> -> </b>
        r'<em\b[^>]*>' : '<i>',     # <em> -> <i>
        r'</em>' : '</i>',          # </em> -> </i>
        r'<h[1-6]\b[^>]*>' : '<b>', # заголовки -> жирный
        r'</h[1-6]>' : '</b>\n',    # закрытие заголовков
    }
    
    # Применяем замены
    cleaned_text = text
    for pattern, replacement in replacements.items():
        cleaned_text = re.sub(pattern, replacement, cleaned_text, flags=re.IGNORECASE)
    
    # Убираем лишние переносы строк
    cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    return cleaned_text

def validate_html_message(text: str) -> tuple[bool, str]:
    """Проверяет корректность HTML разметки для Telegram."""
    if not text:
        return True, ""
    
    # Разрешенные теги в Telegram
    allowed_tags = ['b', 'i', 'u', 's', 'code', 'pre', 'a']
    
    # Находим все теги в сообщении
    tags = re.findall(r'</?(\w+)(?:\s[^>]*)?>', text, re.IGNORECASE)
    
    # Проверяем неразрешенные теги
    invalid_tags = [tag for tag in tags if tag.lower() not in allowed_tags]
    
    if invalid_tags:
        unique_invalid = list(set(invalid_tags))
        return False, f"Неподдерживаемые теги: {', '.join(unique_invalid)}"
    
    return True, ""

async def safe_send_message(bot_or_message, chat_id: str = None, text: str = "", **kwargs) -> bool:
    """Безопасная отправка сообщения с обработкой HTML ошибок."""
    try:
        if hasattr(bot_or_message, 'answer'):  # Это объект message
            await bot_or_message.answer(text, **kwargs)
        else:  # Это объект bot
            await bot_or_message.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except TelegramBadRequest as e:
        if "can't parse entities" in str(e).lower():
            # Пробуем отправить без HTML разметки
            kwargs_no_html = kwargs.copy()
            kwargs_no_html.pop('parse_mode', None)
            try:
                if hasattr(bot_or_message, 'answer'):
                    await bot_or_message.answer(f"⚠️ Ошибка HTML разметки. Сообщение без форматирования:\n\n{text}", **kwargs_no_html)
                else:
                    await bot_or_message.send_message(chat_id=chat_id, text=f"⚠️ Ошибка HTML разметки. Сообщение без форматирования:\n\n{text}", **kwargs_no_html)
                return True
            except Exception:
                return False
        else:
            print(f"Ошибка отправки сообщения: {e}")
            return False
    except Exception as e:
        print(f"Неожиданная ошибка при отправке: {e}")
        return False

def get_cancel_admin_keyboard():
    """Создает клавиатуру с кнопкой отмены для админки"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить создание")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cancel_keyboard():
    """Создает клавиатуру с кнопкой отмены"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить ввод")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Подписки"), KeyboardButton(text="🎟 Промокоды")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Уведомления")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_subscriptions_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать подписку"), KeyboardButton(text="🗑 Удалить подписку")],
            [KeyboardButton(text="◀️ Назад к админке")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_promocodes_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Создать промокод"), KeyboardButton(text="🗑 Удалить промокод")],
            [KeyboardButton(text="◀️ Назад к админке")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_statistics_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📈 Общая статистика"), KeyboardButton(text="📊 Популярные планы")],
            [KeyboardButton(text="📅 Дневная активность")],
            [KeyboardButton(text="◀️ Назад к админке")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_notifications_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Всем пользователям")],
            [KeyboardButton(text="✅ С активной подпиской"), KeyboardButton(text="❌ Без подписки")],
            [KeyboardButton(text="◀️ Назад к админке")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_notification_confirm_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Отправить"), KeyboardButton(text="✏️ Изменить сообщение")],
            [KeyboardButton(text="❌ Отменить рассылку")]
        ],
        resize_keyboard=True
    )
    return keyboard

async def _is_admin(telegram_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = res.scalar_one_or_none()
        return bool(user and user.is_admin)

# ============ АДМИН ПАНЕЛЬ ============

@router.message(Command("admin"))
async def admin_entry(message: types.Message):
    telegram_id = str(message.from_user.id)
    is_admin = await _is_admin(telegram_id)
    
    if not is_admin:
        return
    
    await message.answer("🛠 Админ-панель", reply_markup=get_admin_main_keyboard())

@router.message(F.text == "📦 Подписки")
async def admin_subscriptions(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("📦 Управление подписками", reply_markup=get_subscriptions_keyboard())

@router.message(F.text == "🎟 Промокоды")
async def admin_promocodes(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("🎟 Управление промокодами", reply_markup=get_promocodes_keyboard())

@router.message(F.text == "📊 Статистика")
async def admin_statistics(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("📊 Статистика бота", reply_markup=get_statistics_keyboard())

@router.message(F.text == "📢 Уведомления")
async def admin_notifications(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    try:
        # Получаем статистику пользователей
        stats = await get_notification_stats()
        
        if not stats:
            stats = {'total_users': 0, 'with_subscription': 0, 'without_subscription': 0}
        
        stats_text = (
            f"📢 <b>Рассылка уведомлений</b>\n\n"
            f"📊 <b>Статистика пользователей:</b>\n"
            f"├ Всего: {stats.get('total_users', 0)}\n"
            f"├ С активной подпиской: {stats.get('with_subscription', 0)}\n"
            f"└ Без подписки: {stats.get('without_subscription', 0)}\n\n"
            f"💡 <b>Выберите целевую аудиторию:</b>"
        )
        
        success = await safe_send_message(
            message, 
            text=stats_text, 
            parse_mode="HTML", 
            reply_markup=get_notifications_keyboard()
        )
        
        if not success:
            await message.answer(
                "📢 Рассылка уведомлений\n\nВыберите целевую аудиторию:",
                reply_markup=get_notifications_keyboard()
            )
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при получении данных: {str(e)}\n\n"
            "Попробуйте позже или обратитесь к разработчику.",
            reply_markup=get_admin_main_keyboard()
        )

@router.message(F.text == "◀️ Назад")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню", reply_markup=await get_main_keyboard(str(message.from_user.id)))

@router.message(F.text == "◀️ Назад к админке")
async def back_to_admin(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("🛠 Админ-панель", reply_markup=get_admin_main_keyboard())

# ---- Подписки ----
@router.message(F.text == "➕ Создать подписку")
async def create_plan_prompt(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    admin_state[message.from_user.id] = "create_plan"
    await message.answer(
        "Введите параметры плана через |:\n"
        "name | alias | price | duration_days\n\n"
        "Пример: Старт | start | 199.99 | 30",
        reply_markup=get_cancel_admin_keyboard()
    )

@router.message(F.text == "🗑 Удалить подписку")
async def delete_plan_menu(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True))
        plans = res.scalars().all()
    if not plans:
        await message.answer("Нет доступных подписок.")
        return
    rows = [[InlineKeyboardButton(text=f"❌ {p.name} ({p.alias})", callback_data=f"delplan:{p.id}")]
            for p in plans]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_plan")])
    
    await message.answer("Выберите план для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith("delplan:"))
async def handle_delete_plan(cb: types.CallbackQuery):
    if not await _is_admin(str(cb.from_user.id)):
        await cb.answer("Нет доступа", show_alert=False)
        return
    plan_id = cb.data.split(":", 1)[1]
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        plan = res.scalar_one_or_none()
        if not plan:
            await cb.answer("Не найдено", show_alert=False)
            return
        plan.is_active = False
        await session.commit()
    await cb.answer("Деактивирован")
    await cb.message.edit_text("Подписка деактивирована.")

# ---- Промокоды ----
@router.message(F.text == "➕ Создать промокод")
async def create_promo_prompt(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    admin_state[message.from_user.id] = "create_promo"
    await message.answer(
        "🎟 <b>Создание промокода</b>\n\n"
        "Введите параметры через символ |:\n"
        "<code>КОД | СКИДКА_% | ЛИМИТ_ИСПОЛЬЗОВАНИЙ | ДАТА_ИСТЕЧЕНИЯ</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>SPRING25 | 25 | 100 | 2026-03-31</code>\n\n"
        "<b>Параметры:</b>\n"
        "• КОД - уникальный код промокода\n"
        "• СКИДКА_% - размер скидки (0-100)\n"
        "• ЛИМИТ - максимальное количество использований\n"
        "• ДАТА - дата истечения в формате YYYY-MM-DD",
        reply_markup=get_cancel_admin_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "🗑 Удалить промокод")
async def delete_promo_menu(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Promocode))
        promos = res.scalars().all()
    if not promos:
        await message.answer("Нет промокодов.")
        return
    rows = [[InlineKeyboardButton(text=f"❌ {p.code}", callback_data=f"delpromo:{p.id}")]
            for p in promos]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_promo")])
    
    await message.answer("Выберите промокод для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(F.data.startswith("delpromo:"))
async def handle_delete_promo(cb: types.CallbackQuery):
    if not await _is_admin(str(cb.from_user.id)):
        await cb.answer("Нет доступа", show_alert=False)
        return
    promo_id = cb.data.split(":", 1)[1]
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Promocode).where(Promocode.id == promo_id))
        await session.commit()
    await cb.answer("Удалено")
    await cb.message.edit_text("Промокод удалён.")

# ---- Обработчики inline кнопок отмены ----
@router.callback_query(F.data == "cancel_delete_plan")
async def handle_cancel_delete_plan(cb: types.CallbackQuery):
    if not await _is_admin(str(cb.from_user.id)):
        await cb.answer("Нет доступа", show_alert=False)
        return
    
    try:
        await cb.message.delete()
        await cb.answer("Операция отменена")
    except Exception as e:
        print(f"🔍 ADMIN: Ошибка при удалении сообщения: {e}")
        await cb.message.edit_text("❌ Операция отменена")
        await cb.answer("Операция отменена")

@router.callback_query(F.data == "cancel_delete_promo")
async def handle_cancel_delete_promo(cb: types.CallbackQuery):
    if not await _is_admin(str(cb.from_user.id)):
        await cb.answer("Нет доступа", show_alert=False)
        return
    
    try:
        await cb.message.delete()
        await cb.answer("Операция отменена")
    except Exception as e:
        print(f"🔍 ADMIN: Ошибка при удалении сообщения: {e}")
        await cb.message.edit_text("❌ Операция отменена")
        await cb.answer("Операция отменена")

@router.message(F.text == "❌ Отменить создание")
async def cancel_creation(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    user_id = message.from_user.id
    if user_id in admin_state:
        admin_state.pop(user_id, None)
    
    await message.answer(
        "❌ <b>Создание отменено</b>\n\n"
        "Операция создания была отменена.",
        reply_markup=get_admin_main_keyboard(),
        parse_mode="HTML"
    )

# ---- Обработка входящих сообщений для админских состояний ----
@router.message(lambda message: message.from_user.id in admin_state)
async def handle_admin_states(message: types.Message):
    user_id = message.from_user.id
    state = admin_state.get(user_id)
    if not state:
        return
    if not await _is_admin(str(user_id)):
        await message.answer("⛔ Доступ запрещён")
        admin_state.pop(user_id, None)
        return

    if state == "create_plan":
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 4:
            await message.answer("Неверный формат. Ожидается: name | alias | price | duration_days")
            return
        name, alias, price_s, days_s = parts
        try:
            price = Decimal(price_s)
            duration_days = int(days_s)
        except Exception:
            await message.answer("Цена или дни указаны неверно")
            return
        async with AsyncSessionLocal() as session:
            plan = SubscriptionPlan(name=name, alias=alias, price=price, duration_days=duration_days, is_active=True)
            session.add(plan)
            await session.commit()
        await message.answer("✅ Подписка создана", reply_markup=get_subscriptions_keyboard())
        admin_state.pop(user_id, None)
        return

    if state == "create_promo":
        parts = [p.strip() for p in message.text.split("|")]
        if len(parts) != 4:
            await message.answer("Неверный формат. Ожидается: CODE | discount_percent | usage_limit | expired_at(YYYY-MM-DD)")
            return
        
        code, discount_s, limit_s, expired_s = parts
        
        # Валидация параметров
        try:
            discount = int(discount_s)
            usage_limit = int(limit_s)
            
            if discount < 0 or discount > 100:
                await message.answer("❌ Скидка должна быть от 0 до 100 процентов")
                return
            
            if usage_limit <= 0:
                await message.answer("❌ Лимит использования должен быть больше 0")
                return
            
            expired_at = datetime.strptime(expired_s, "%Y-%m-%d")
            
            if expired_at <= datetime.utcnow():
                await message.answer("❌ Дата истечения должна быть в будущем")
                return
                
        except ValueError as e:
            if "time data" in str(e):
                await message.answer("❌ Неверный формат даты. Используйте YYYY-MM-DD")
            else:
                await message.answer("❌ Неверный формат числовых параметров")
            return
        except Exception as e:
            await message.answer(f"❌ Ошибка валидации: {str(e)}")
            return
        
        # Создаем промокод
        try:
            async with AsyncSessionLocal() as session:
                promo = Promocode(
                    code=code.upper(),
                    discount_percent=discount, 
                    usage_limit=usage_limit, 
                    expired_at=expired_at
                )
                session.add(promo)
                await session.commit()
                
            await message.answer(
                f"✅ <b>Промокод создан успешно!</b>\n\n"
                f"🎟 Код: <code>{code.upper()}</code>\n"
                f"💰 Скидка: {discount}%\n"
                f"📊 Лимит: {usage_limit} использований\n"
                f"📅 Действует до: {expired_at.strftime('%d.%m.%Y')}",
                reply_markup=get_promocodes_keyboard(),
                parse_mode="HTML"
            )
            admin_state.pop(user_id, None)
            
        except Exception as e:
            if "unique constraint" in str(e).lower():
                await message.answer("❌ Промокод с таким кодом уже существует")
            else:
                await message.answer(f"❌ Ошибка создания промокода: {str(e)}")
            return

# ============ ПОЛЬЗОВАТЕЛЬСКИЕ ПРОМОКОДЫ ============

@router.message(lambda message: message.text == "🎟 Ввести промокод")
async def enter_promocode_prompt(message: types.Message):
    """Обработчик кнопки ввода промокода"""
    print(f"🔍 PROMOCODES HANDLER: ===== НАЧАЛО ОБРАБОТКИ КНОПКИ ПРОМОКОДА =====")
    print(f"🔍 PROMOCODES HANDLER: Получено сообщение '{message.text}' от пользователя {message.from_user.id}")
    
    telegram_id = str(message.from_user.id)
    
    # Устанавливаем состояние
    promo_state[message.from_user.id] = "enter_promo"
    print(f"🔍 PROMOCODES HANDLER: Установлено состояние 'enter_promo' для пользователя {message.from_user.id}")
    
    await message.answer(
        "🎟 <b>Введите промокод</b>\n\n"
        "Введите код промокода для получения скидки на самую дешевую подписку.\n"
        "Промокод можно использовать многократно!",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )

@router.message(lambda message: message.text == "❌ Отменить ввод")
async def cancel_promocode_input(message: types.Message):
    """Обработчик кнопки отмены ввода промокода"""
    print(f"🔍 PROMOCODES HANDLER: ===== ОТМЕНА ВВОДА ПРОМОКОДА =====")
    
    user_id = message.from_user.id
    
    # Убираем состояние
    if user_id in promo_state:
        promo_state.pop(user_id, None)
    
    # Возвращаем главную клавиатуру
    keyboard = await get_main_keyboard(str(user_id))
    await message.answer(
        "❌ <b>Ввод промокода отменен</b>\n\n"
        "Вы можете попробовать ввести промокод позже.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.message(lambda message: (
    message.text and 
    message.text not in {"🎟 Ввести промокод", "❌ Отменить ввод"} and
    message.from_user.id in promo_state and 
    promo_state[message.from_user.id] == "enter_promo" and
    "avito.ru" not in message.text.lower()  # Исключаем ссылки на Avito
))
async def handle_promocode_input(message: types.Message):
    """Обработчик ввода промокода"""
    user_id = message.from_user.id
    
    promo_code = message.text.strip().upper()
    
    try:
        async with AsyncSessionLocal() as session:
            # Ищем промокод в базе данных
            result = await session.execute(
                select(Promocode).where(Promocode.code == promo_code)
            )
            promocode = result.scalar_one_or_none()
            
            if not promocode:
                await message.answer("❌ Промокод не найден")
                return
            
            # Проверяем, не истек ли промокод
            if promocode.expired_at <= datetime.utcnow():
                await message.answer("❌ Промокод истек")
                return
            
            # Проверяем, не исчерпан ли лимит использования
            if promocode.used_count >= promocode.usage_limit:
                await message.answer("❌ Лимит использования промокода исчерпан")
                return
            
            # Получаем пользователя
            user_result = await session.execute(
                select(User).where(User.telegram_id == str(user_id))
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                return
            
            # Увеличиваем счетчик использования промокода
            promocode.used_count += 1
            await session.commit()
            
            # Сохраняем промокод в БД для применения при оплате
            from ...db.repository import set_user_active_promocode
            await set_user_active_promocode(str(user_id), promocode)
            
            # Убираем состояние
            promo_state.pop(user_id, None)
            
            await message.answer(
                f"✅ <b>Промокод активирован!</b>\n\n"
                f"🎟 Код: {promocode.code}\n"
                f"💰 Скидка: {promocode.discount_percent}%\n"
                f"📅 Действует до: {promocode.expired_at.strftime('%d.%m.%Y')}\n\n"
                f"💡 <b>Важно:</b> Скидка будет применена только к самой дешевой подписке!",
                parse_mode="HTML",
                reply_markup=await get_main_keyboard(str(user_id))
            )
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при применении промокода: {str(e)}")
        promo_state.pop(user_id, None)


# =================== СТАТИСТИКА ===================

@router.message(F.text == "📈 Общая статистика")
async def admin_general_stats(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    try:
        # Получаем статистику
        stats = await get_monthly_statistics()
        
        if not stats:
            await message.answer("❌ Не удалось получить статистику")
            return
        
        # Форматируем статистику
        stats_text = (
            f"📊 <b>Общая статистика (за {stats['period_days']} дней)</b>\n\n"
            f"👥 <b>Пользователи:</b>\n"
            f"├ Всего: {stats['total_users']}\n"
            f"├ Новых за месяц: {stats['new_users_month']}\n"
            f"└ С активной подпиской: {stats['active_subscriptions']}\n\n"
            f"💰 <b>Финансы:</b>\n"
            f"├ Доход за месяц: {stats['total_revenue_month']:.2f} ₽\n"
            f"└ Успешных платежей: {stats['successful_payments_month']}\n\n"
            f"🎟 <b>Промокоды:</b>\n"
            f"└ Использовано за месяц: {stats['used_promos_month']}\n\n"
            f"🔍 <b>Отслеживания:</b>\n"
            f"└ Активных: {stats['active_trackings']}\n\n"
            f"📅 <i>Обновлено: {stats['generated_at'].strftime('%d.%m.%Y %H:%M')}</i>"
        )
        
        await message.answer(stats_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статистики: {str(e)}")


@router.message(F.text == "📊 Популярные планы")
async def admin_popular_plans(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    try:
        plans = await get_popular_subscription_plans()
        
        if not plans:
            await message.answer("📊 За последний месяц подписок не было")
            return
        
        plans_text = "📊 <b>Популярные планы подписок (за 30 дней)</b>\n\n"
        
        for i, plan in enumerate(plans, 1):
            plans_text += (
                f"{i}. <b>{plan['name']}</b>\n"
                f"   💰 Цена: {plan['price']:.2f} ₽\n"
                f"   🛒 Покупок: {plan['purchases']}\n\n"
            )
        
        await message.answer(plans_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статистики планов: {str(e)}")


@router.message(F.text == "📅 Дневная активность")
async def admin_daily_activity(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    try:
        daily_stats = await get_daily_activity_stats(7)
        
        if not daily_stats:
            await message.answer("❌ Не удалось получить дневную статистику")
            return
        
        activity_text = "📅 <b>Активность за последние 7 дней</b>\n\n"
        
        for day in daily_stats:
            activity_text += (
                f"📆 <b>{day['date']}</b>\n"
                f"├ Новых пользователей: {day['new_users']}\n"
                f"└ Успешных платежей: {day['successful_payments']}\n\n"
            )
        
        await message.answer(activity_text, parse_mode="HTML")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении дневной статистики: {str(e)}")


# =================== УВЕДОМЛЕНИЯ ===================

@router.message(F.text == "👥 Всем пользователям")
async def notification_to_all(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    admin_id = str(message.from_user.id)
    notification_state[admin_id] = {"target": "all", "message": None}
    
    await message.answer(
        "📝 <b>Введите сообщение для рассылки всем пользователям:</b>\n\n"
        "💡 <i>Поддерживается HTML разметка:</i>\n"
        "• &lt;b&gt;жирный&lt;/b&gt; - <b>жирный</b>\n"
        "• &lt;i&gt;курсив&lt;/i&gt; - <i>курсив</i>\n"
        "• &lt;code&gt;код&lt;/code&gt; - <code>код</code>\n"
        "• &lt;u&gt;подчеркнутый&lt;/u&gt; - <u>подчеркнутый</u>\n\n"
        "⚠️ <i>Неподдерживаемые теги будут автоматически исправлены</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_admin_keyboard()
    )

@router.message(F.text == "✅ С активной подпиской")
async def notification_to_active(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    admin_id = str(message.from_user.id)
    notification_state[admin_id] = {"target": "active", "message": None}
    
    await message.answer(
        "📝 <b>Введите сообщение для пользователей с активной подпиской:</b>\n\n"
        "💡 <i>Поддерживается HTML разметка:</i>\n"
        "• &lt;b&gt;жирный&lt;/b&gt; - <b>жирный</b>\n"
        "• &lt;i&gt;курсив&lt;/i&gt; - <i>курсив</i>\n"
        "• &lt;code&gt;код&lt;/code&gt; - <code>код</code>\n"
        "• &lt;u&gt;подчеркнутый&lt;/u&gt; - <u>подчеркнутый</u>\n\n"
        "⚠️ <i>Неподдерживаемые теги будут автоматически исправлены</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_admin_keyboard()
    )

@router.message(F.text == "❌ Без подписки")
async def notification_to_inactive(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    admin_id = str(message.from_user.id)
    notification_state[admin_id] = {"target": "inactive", "message": None}
    
    await message.answer(
        "📝 <b>Введите сообщение для пользователей без активной подписки:</b>\n\n"
        "💡 <i>Поддерживается HTML разметка:</i>\n"
        "• &lt;b&gt;жирный&lt;/b&gt; - <b>жирный</b>\n"
        "• &lt;i&gt;курсив&lt;/i&gt; - <i>курсив</i>\n"
        "• &lt;code&gt;код&lt;/code&gt; - <code>код</code>\n"
        "• &lt;u&gt;подчеркнутый&lt;/u&gt; - <u>подчеркнутый</u>\n\n"
        "⚠️ <i>Неподдерживаемые теги будут автоматически исправлены</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_admin_keyboard()
    )

@router.message(F.text == "✅ Отправить")
async def confirm_notification(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    admin_id = str(message.from_user.id)
    if admin_id not in notification_state or not notification_state[admin_id].get("message"):
        await message.answer("❌ Нет подготовленного сообщения", reply_markup=get_admin_main_keyboard())
        return
    
    await send_notification_to_users(message, admin_id)

@router.message(F.text == "✏️ Изменить сообщение")
async def edit_notification_message(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    admin_id = str(message.from_user.id)
    if admin_id not in notification_state:
        await message.answer("❌ Нет активной рассылки", reply_markup=get_admin_main_keyboard())
        return
    
    target_text = {
        "all": "всем пользователям",
        "active": "пользователям с активной подпиской", 
        "inactive": "пользователям без подписки"
    }.get(notification_state[admin_id]["target"], "выбранной аудитории")
    
    # Сбрасываем сообщение для ввода нового
    notification_state[admin_id]["message"] = None
    
    await message.answer(
        f"📝 <b>Введите новое сообщение для {target_text}:</b>\n\n"
        "💡 <i>Поддерживается HTML разметка:</i>\n"
        "• &lt;b&gt;жирный&lt;/b&gt; - <b>жирный</b>\n"
        "• &lt;i&gt;курсив&lt;/i&gt; - <i>курсив</i>\n"
        "• &lt;code&gt;код&lt;/code&gt; - <code>код</code>\n"
        "• &lt;u&gt;подчеркнутый&lt;/u&gt; - <u>подчеркнутый</u>\n\n"
        "⚠️ <i>Неподдерживаемые теги будут автоматически исправлены</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_admin_keyboard()
    )

@router.message(F.text == "❌ Отменить рассылку")
async def cancel_notification(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    
    admin_id = str(message.from_user.id)
    notification_state.pop(admin_id, None)
    
    await message.answer(
        "❌ <b>Рассылка отменена</b>",
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )

async def send_notification_to_users(message: types.Message, admin_id: str):
    """Отправляет уведомление выбранной группе пользователей"""
    try:
        state = notification_state[admin_id]
        target = state["target"]
        text = state["message"]
        
        # Получаем список пользователей
        if target == "all":
            users = await get_all_users()
            target_name = "всем пользователям"
        elif target == "active":
            users = await get_users_with_active_subscription()
            target_name = "пользователям с активной подпиской"
        elif target == "inactive":
            users = await get_users_without_active_subscription()
            target_name = "пользователям без подписки"
        else:
            await message.answer("❌ Неизвестный тип рассылки", reply_markup=get_admin_main_keyboard())
            return
        
        if not users:
            await message.answer(f"📭 Нет пользователей для рассылки ({target_name})", reply_markup=get_admin_main_keyboard())
            notification_state.pop(admin_id, None)
            return
        
        # Показываем прогресс
        progress_msg = await message.answer(
            f"📤 <b>Начинаю рассылку {target_name}...</b>\n"
            f"👥 Всего получателей: {len(users)}",
            parse_mode="HTML"
        )
        
        # Отправляем сообщения
        success_count = 0
        failed_count = 0
        html_error_count = 0
        bot = message.bot
        
        for i, user in enumerate(users, 1):
            try:
                # Безопасная отправка с обработкой HTML ошибок
                success = await safe_send_message(
                    bot,
                    chat_id=user['telegram_id'],
                    text=text,
                    parse_mode="HTML"
                )
                
                if success:
                    success_count += 1
                else:
                    # Пробуем отправить без HTML разметки как fallback
                    try:
                        await bot.send_message(
                            chat_id=user['telegram_id'],
                            text=f"⚠️ Сообщение от администрации (без форматирования):\n\n{text}"
                        )
                        success_count += 1
                        html_error_count += 1
                    except Exception:
                        failed_count += 1
                
                # Обновляем прогресс каждые 10 сообщений
                if i % 10 == 0 or i == len(users):
                    try:
                        progress_text = (
                            f"📤 <b>Рассылка в процессе...</b>\n"
                            f"👥 Всего: {len(users)}\n"
                            f"✅ Отправлено: {success_count}\n"
                            f"❌ Ошибок: {failed_count}\n"
                            f"📊 Прогресс: {i}/{len(users)}"
                        )
                        if html_error_count > 0:
                            progress_text += f"\n⚠️ HTML ошибок: {html_error_count}"
                        
                        await progress_msg.edit_text(progress_text, parse_mode="HTML")
                    except:
                        pass  # Игнорируем ошибки редактирования
                
                # Пауза для избежания лимитов
                await asyncio.sleep(0.05)  # 50ms между сообщениями
                
            except Exception as e:
                failed_count += 1
                print(f"Ошибка отправки пользователю {user['telegram_id']}: {e}")
        
        # Финальный отчет
        final_report = (
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"├ Всего получателей: {len(users)}\n"
            f"├ Успешно доставлено: {success_count}\n"
            f"├ Ошибок доставки: {failed_count}"
        )
        
        if html_error_count > 0:
            final_report += f"\n├ HTML ошибок (отправлено без форматирования): {html_error_count}"
        
        final_report += f"\n└ Процент успеха: {(success_count / len(users) * 100) if len(users) > 0 else 0:.1f}%"
        
        try:
            await progress_msg.edit_text(final_report, parse_mode="HTML")
        except Exception as e:
            # Fallback без HTML если есть проблемы с разметкой
            await progress_msg.edit_text(final_report.replace('<b>', '').replace('</b>', ''))
        
        # Убираем состояние
        notification_state.pop(admin_id, None)
        
        await message.answer("🏠 Возвращаемся в админ-панель", reply_markup=get_admin_main_keyboard())
        
    except Exception as e:
        await message.answer(f"❌ Критическая ошибка рассылки: {str(e)}", reply_markup=get_admin_main_keyboard())
        notification_state.pop(admin_id, None)


# Обработчик текстовых сообщений для уведомлений
@router.message(lambda message: str(message.from_user.id) in notification_state and notification_state[str(message.from_user.id)].get("message") is None)
async def handle_notification_text(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        return
    
    admin_id = str(message.from_user.id)
    
    # Отменяем, если это команда отмены
    if message.text == "❌ Отменить создание":
        notification_state.pop(admin_id, None)
        await message.answer("❌ Создание уведомления отменено", reply_markup=get_admin_main_keyboard())
        return
    
    try:
        # Проверяем и очищаем HTML разметку
        original_text = message.text
        is_valid, error_msg = validate_html_message(original_text)
        
        if not is_valid:
            # Автоматически исправляем сообщение
            cleaned_text = clean_html_message(original_text)
            notification_state[admin_id]["message"] = cleaned_text
            
            await message.answer(
                f"⚠️ <b>HTML разметка исправлена</b>\n\n"
                f"❌ <b>Проблема:</b> {error_msg}\n"
                f"✅ <b>Неподдерживаемые теги автоматически заменены/удалены</b>\n\n"
                f"💡 <i>Разрешенные теги: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;s&gt;, &lt;code&gt;, &lt;pre&gt;, &lt;a&gt;</i>",
                parse_mode="HTML"
            )
        else:
            # Сохраняем оригинальное сообщение
            notification_state[admin_id]["message"] = original_text
        
        # Получаем информацию о получателях
        target = notification_state[admin_id]["target"]
        try:
            stats = await get_notification_stats()
            if target == "all":
                count = stats["total_users"]
                target_name = "всем пользователям"
            elif target == "active":
                count = stats["with_subscription"]
                target_name = "пользователям с активной подпиской"
            elif target == "inactive":
                count = stats["without_subscription"]
                target_name = "пользователям без подписки"
            else:
                count = 0
                target_name = "неизвестной группе"
        except Exception as e:
            count = 0
            target_name = "получателям (ошибка подсчета)"
            print(f"Ошибка получения статистики: {e}")
        
        # Получаем финальное сообщение для предпросмотра
        final_message = notification_state[admin_id]["message"]
        
        # Показываем предпросмотр
        preview_text = (
            f"📋 <b>Предпросмотр уведомления</b>\n\n"
            f"👥 <b>Получатели:</b> {target_name} ({count} чел.)\n\n"
            f"📝 <b>Сообщение:</b>\n"
            f"{'─' * 30}\n"
            f"{final_message}\n"
            f"{'─' * 30}\n\n"
            f"⚠️ <b>Подтвердите отправку:</b>"
        )
        
        # Безопасно отправляем предпросмотр
        success = await safe_send_message(
            message, 
            text=preview_text, 
            parse_mode="HTML", 
            reply_markup=get_notification_confirm_keyboard()
        )
        
        if not success:
            await message.answer(
                "❌ Ошибка отправки предпросмотра. Попробуйте упростить HTML разметку.",
                reply_markup=get_notification_confirm_keyboard()
            )
            
    except Exception as e:
        await message.answer(
            f"❌ Произошла ошибка при обработке сообщения: {str(e)}\n\n"
            "Попробуйте отправить сообщение без HTML разметки.",
            reply_markup=get_admin_main_keyboard()
        )
        notification_state.pop(admin_id, None)
