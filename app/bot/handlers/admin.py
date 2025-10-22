from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, delete
from decimal import Decimal
from ...db.model import AsyncSessionLocal, User, SubscriptionPlan, Promocode
from .start import get_main_keyboard

router = Router()

# Простейшее состояние админских операций (без FSM)
admin_state = {}

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

@router.message(Command("admin"))
async def admin_entry(message: types.Message):
    telegram_id = str(message.from_user.id)
    is_admin = await _is_admin(telegram_id)
    
    if not is_admin:
        # Не отвечаем пользователям без прав админа
        return
    
    await message.answer("🛠 Админ-панель", reply_markup=get_admin_main_keyboard())

@router.message(lambda m: m.text == "📦 Подписки")
async def admin_subscriptions(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("📦 Управление подписками", reply_markup=get_subscriptions_keyboard())

@router.message(lambda m: m.text == "🎟 Промокоды")
async def admin_promocodes(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("🎟 Управление промокодами", reply_markup=get_promocodes_keyboard())

@router.message(lambda m: m.text == "◀️ Назад")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню", reply_markup=await get_main_keyboard(str(message.from_user.id)))

@router.message(lambda m: m.text == "◀️ Назад к админке")
async def back_to_admin(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    await message.answer("🛠 Админ-панель", reply_markup=get_admin_main_keyboard())

# ---- Подписки ----
@router.message(lambda m: m.text == "➕ Создать подписку")
async def create_plan_prompt(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    admin_state[message.from_user.id] = "create_plan"
    await message.answer(
        "Введите параметры плана через |:\n"
        "name | alias | price | duration_days\n\n"
        "Пример: Старт | start | 199.99 | 30"
    )

@router.message(lambda m: m.text == "🗑 Удалить подписку")
async def delete_plan_menu(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active == True))
        plans = res.scalars().all()
    if not plans:
        await message.answer("Нет доступных планов.")
        return
    rows = [[InlineKeyboardButton(text=f"❌ {p.name} ({p.alias})", callback_data=f"delplan:{p.id}")]
            for p in plans]
    await message.answer("Выберите план для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(lambda c: c.data and c.data.startswith("delplan:"))
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
    await cb.message.edit_text("План деактивирован (is_active = false).")

# ---- Промокоды ----
@router.message(lambda m: m.text == "➕ Создать промокод")
async def create_promo_prompt(message: types.Message):
    if not await _is_admin(str(message.from_user.id)):
        await message.answer("⛔ Доступ запрещён")
        return
    admin_state[message.from_user.id] = "create_promo"
    await message.answer(
        "Введите параметры промокода через |:\n"
        "CODE | discount_percent | usage_limit | expired_at(YYYY-MM-DD)\n\n"
        "Пример: SPRING25 | 25 | 100 | 2026-03-31"
    )

@router.message(lambda m: m.text == "🗑 Удалить промокод")
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
    await message.answer("Выберите промокод для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(lambda c: c.data and c.data.startswith("delpromo:"))
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

# ---- Обработка входящих сообщений для состояний ----
@router.message()
async def handle_admin_states(message: types.Message):
    # Исключаем команды, которые должны обрабатываться другими роутерами
    if message.text and message.text.startswith('/'):
        return
    
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
        try:
            discount = int(discount_s)
            usage_limit = int(limit_s)
            expired_at = types.datetime.datetime.strptime(expired_s, "%Y-%m-%d")
        except Exception:
            await message.answer("Параметры промокода указаны неверно")
            return
        from datetime import datetime
        try:
            expired_at = datetime.strptime(expired_s, "%Y-%m-%d")
        except Exception:
            await message.answer("Дата должна быть в формате YYYY-MM-DD")
            return
        async with AsyncSessionLocal() as session:
            promo = Promocode(code=code, discount_percent=discount, usage_limit=usage_limit, expired_at=expired_at)
            session.add(promo)
            await session.commit()
        await message.answer("✅ Промокод создан", reply_markup=get_promocodes_keyboard())
        admin_state.pop(user_id, None)
        return


