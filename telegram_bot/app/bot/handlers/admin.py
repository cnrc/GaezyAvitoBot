"""
Административные функции и работа с промокодами
"""
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, delete
from decimal import Decimal
from datetime import datetime
from ...db.model import AsyncSessionLocal, User, SubscriptionPlan, Promocode
from .base import get_main_keyboard

router = Router()

# Простейшее состояние админских операций (без FSM)
admin_state = {}
promo_state = {}  # Состояние для ввода промокода пользователем

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
