"""
Обработчики для работы с промокодами
"""
from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select
from datetime import datetime
from ...db.model import AsyncSessionLocal, User, Promocode, PromoUsage, user_has_used_promocode, get_user_active_promocode, set_user_active_promocode
from .start import get_main_keyboard

router = Router()

# Состояние для ввода промокода
promo_state = {}

print("🔍 PROMOCODES MODULE: Модуль promocodes.py загружен")

def get_cancel_keyboard():
    """Создает клавиатуру с кнопкой отмены"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить ввод")]
        ],
        resize_keyboard=True
    )
    return keyboard

@router.message(lambda message: message.text == "🎟 Ввести промокод")
async def enter_promocode_prompt(message: types.Message):
    """Обработчик кнопки ввода промокода"""
    print(f"🔍 PROMOCODES HANDLER: ===== НАЧАЛО ОБРАБОТКИ КНОПКИ ПРОМОКОДА =====")
    print(f"🔍 PROMOCODES HANDLER: Получено сообщение '{message.text}' от пользователя {message.from_user.id}")
    print(f"🔍 PROMOCODES HANDLER: Текст сообщения: '{message.text}'")
    print(f"🔍 PROMOCODES HANDLER: Начинаем обработку кнопки ввода промокода")
    
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
    print(f"🔍 PROMOCODES HANDLER: Отправлено сообщение пользователю {message.from_user.id}")

@router.message(lambda message: message.text == "❌ Отменить ввод")
async def cancel_promocode_input(message: types.Message):
    """Обработчик кнопки отмены ввода промокода"""
    print(f"🔍 PROMOCODES HANDLER: ===== ОТМЕНА ВВОДА ПРОМОКОДА =====")
    print(f"🔍 PROMOCODES HANDLER: Получена кнопка отмены от пользователя {message.from_user.id}")
    
    user_id = message.from_user.id
    
    # Убираем состояние
    if user_id in promo_state:
        promo_state.pop(user_id, None)
        print(f"🔍 PROMOCODES HANDLER: Убрано состояние для пользователя {user_id}")
    
    # Возвращаем главную клавиатуру
    keyboard = await get_main_keyboard(str(user_id))
    await message.answer(
        "❌ <b>Ввод промокода отменен</b>\n\n"
        "Вы можете попробовать ввести промокод позже.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    print(f"🔍 PROMOCODES HANDLER: Отправлено сообщение об отмене пользователю {user_id}")

@router.message(lambda message: message.text != "🎟 Ввести промокод" and message.text != "❌ Отменить ввод")
async def handle_promocode_input(message: types.Message):
    """Обработчик ввода промокода"""
    user_id = message.from_user.id
    
    # Проверяем, находится ли пользователь в состоянии ввода промокода
    if user_id not in promo_state or promo_state[user_id] != "enter_promo":
        return
    
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
            
            # Сохраняем промокод в временное хранилище для применения при оплате
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


