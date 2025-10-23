"""
Обработчики для покупки подписки и платежей
"""
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from sqlalchemy import select
from decimal import Decimal
from datetime import datetime, timedelta
from ...db.model import AsyncSessionLocal, User, SubscriptionPlan, Payment, UserSubscription, Promocode, PromoUsage, get_user_active_promocode, get_user_current_promocode, clear_user_promocode
from .start import get_main_keyboard
from ...config import YOOKASSA_TOKEN

router = Router()

async def get_subscription_plans_keyboard(telegram_id: str = None):
    """Создает клавиатуру с доступными планами подписки"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
            )
            plans = result.scalars().all()
        
        if not plans:
            return None
        
        # Получаем активный промокод пользователя
        user_promocode = None
        if telegram_id:
            try:
                user_promocode = await get_user_current_promocode(telegram_id)
            except Exception:
                pass
        
        # Находим самую дешевую подписку
        cheapest_plan = min(plans, key=lambda p: float(p.price))
        
        keyboard_buttons = []
        for plan in plans:
            if user_promocode and plan.id == cheapest_plan.id:
                # Применяем скидку только к самой дешевой подписке
                discount_amount = float(plan.price) * (user_promocode.discount_percent / 100)
                discounted_price = float(plan.price) - discount_amount
                button_text = f"{plan.name} - {discounted_price:.2f} ₽ (скидка {user_promocode.discount_percent}%)"
            else:
                button_text = f"{plan.name} - {plan.price} ₽"
            
            callback_data = f"buy_plan:{plan.id}"
            keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])
        
        # Добавляем кнопку "Отмена"
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy")])

        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None

@router.message(lambda m: m.text == "💳 Купить подписку")
async def buy_subscription(message: types.Message):
    """Обработчик кнопки покупки подписки"""
    print(f"🔍 PAYMENTS HANDLER: Получена кнопка '💳 Купить подписку' от пользователя {message.from_user.id}")
    
    try:
        keyboard = await get_subscription_plans_keyboard(str(message.from_user.id))
        
        if not keyboard:
            await message.answer(
                "❌ <b>Планы подписки недоступны</b>\n\n"
                "Обратитесь к администратору для настройки планов подписки.",
                parse_mode="HTML"
            )
            return
        
        await message.answer(
            "💳 <b>Выберите план подписки</b>\n\n"
            "Нажмите на подходящий план для оплаты:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()

@router.callback_query(lambda c: c.data and c.data.startswith("buy_plan:"))
async def handle_buy_plan(callback: types.CallbackQuery):
    """Обработчик выбора плана подписки"""
    plan_id = callback.data.split(":", 1)[1]
    
    async with AsyncSessionLocal() as session:
        # Получаем план подписки
        result = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        plan = result.scalar_one_or_none()
        
        if not plan:
            await callback.answer("❌ План не найден", show_alert=True)
            return
        
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == str(callback.from_user.id))
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        try:
            # Получаем активный промокод пользователя
            user_promocode = await get_user_current_promocode(str(callback.from_user.id))
            
            # Находим самую дешевую подписку для проверки применения скидки
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
                )
                all_plans = result.scalars().all()
                cheapest_plan = min(all_plans, key=lambda p: float(p.price))
            
            # Рассчитываем цену
            if user_promocode and plan.id == cheapest_plan.id:
                # Применяем скидку только к самой дешевой подписке
                discount_amount = float(plan.price) * (user_promocode.discount_percent / 100)
                final_price = float(plan.price) - discount_amount
                title = f"Подписка {plan.name} (скидка {user_promocode.discount_percent}%)"
                description = f"Подписка на {plan.duration_days} дней для мониторинга цен на Avito\n🎟 Промокод: {user_promocode.code}"
            else:
                final_price = float(plan.price)
                title = f"Подписка {plan.name}"
                description = f"Подписка на {plan.duration_days} дней для мониторинга цен на Avito"
            
            # Создаем инвойс через Telegram
            await callback.bot.send_invoice(
                chat_id=callback.from_user.id,
                title=title,
                description=description,
                payload=f"subscription_{plan.id}_{user.id}",  # Уникальный payload
                provider_token=YOOKASSA_TOKEN,  # Для тестового режима используем TEST
                currency="RUB",
                prices=[LabeledPrice(label=f"Подписка {plan.name}", amount=int(final_price * 100))],  # Сумма в копейках
                start_parameter=f"subscription_{plan.id}",
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                send_phone_number_to_provider=False,
                send_email_to_provider=False,
                is_flexible=False,
                disable_notification=False,
                protect_content=False,
                reply_to_message_id=None,
                allow_sending_without_reply=False,
                reply_markup=None,
                request_timeout=30
            )
            
            await callback.answer()
            
        except Exception as e:
            print(f"Ошибка при создании инвойса: {e}")
            await callback.answer("❌ Ошибка при создании инвойса", show_alert=True)


@router.callback_query(lambda c: c.data == "cancel_buy")
async def handle_cancel_buy(callback: types.CallbackQuery):
    """Отмена выбора подписки: удаляет сообщение с планами"""
    try:
        await callback.message.delete()
    except Exception:
        # Если удалить нельзя (например, старая версия или нет прав) — убираем разметку
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Отменено")

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    """Обработчик pre-checkout запроса"""
    try:
        # Проверяем payload
        payload = pre_checkout_query.invoice_payload
        if not payload.startswith("subscription_"):
            await pre_checkout_query.answer(ok=False, error_message="Неверный тип платежа")
            return
        
        # Парсим payload
        parts = payload.split("_")
        if len(parts) != 3:
            await pre_checkout_query.answer(ok=False, error_message="Неверный формат платежа")
            return
        
        plan_id = parts[1]
        user_id = parts[2]
        
        # Проверяем существование плана
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()
            
            if not plan:
                await pre_checkout_query.answer(ok=False, error_message="План подписки не найден")
                return
            
            # Проверяем пользователя
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await pre_checkout_query.answer(ok=False, error_message="Пользователь не найден")
                return
        
        # Подтверждаем платеж
        await pre_checkout_query.answer(ok=True)
        
    except Exception as e:
        print(f"Ошибка при обработке pre-checkout: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка обработки платежа")

@router.message(lambda m: m.content_type == types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    """Обработчик успешного платежа"""
    try:
        payment = message.successful_payment
        payload = payment.invoice_payload
        
        # Парсим payload
        parts = payload.split("_")
        if len(parts) != 3:
            await message.answer("❌ Ошибка обработки платежа")
            return
        
        plan_id = parts[1]
        user_id = parts[2]
        
        async with AsyncSessionLocal() as session:
            # Получаем план
            plan_result = await session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
            )
            plan = plan_result.scalar_one_or_none()
            
            if not plan:
                await message.answer("❌ План подписки не найден")
                return
            
            # Получаем пользователя
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                await message.answer("❌ Пользователь не найден")
                return
            
            # Создаем запись о платеже
            payment_record = Payment(
                user_id=user.id,
                plan_id=plan.id,
                provider="ЮКасса",
                transaction_id=payment.telegram_payment_charge_id,
                status=True
            )
            session.add(payment_record)
            
            # Создаем подписку
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=plan.duration_days)
            
            subscription = UserSubscription(
                user_id=user.id,
                plan_id=plan.id,
                start_date=start_date,
                end_date=end_date
            )
            session.add(subscription)
            
            # Проверяем, была ли применена скидка (только для самой дешевой подписки)
            user_promocode = await get_user_current_promocode(str(message.from_user.id))
            promo_applied = False
            
            if user_promocode:
                # Находим самую дешевую подписку
                result_all_plans = await session.execute(
                    select(SubscriptionPlan).where(SubscriptionPlan.is_active == True)
                )
                all_plans = result_all_plans.scalars().all()
                cheapest_plan = min(all_plans, key=lambda p: float(p.price))
                
                if plan.id == cheapest_plan.id:
                    # Записываем использование промокода только для самой дешевой подписки
                    promo_usage = PromoUsage(
                        user_id=user.id,
                        promo_id=user_promocode.id
                    )
                    session.add(promo_usage)
                    
                    # Увеличиваем счетчик использования промокода
                    promocode_result = await session.execute(
                        select(Promocode).where(Promocode.id == user_promocode.id)
                    )
                    promocode_obj = promocode_result.scalar_one_or_none()
                    if promocode_obj:
                        promocode_obj.used_count += 1
                    
                    promo_applied = True
                    
                    # Очищаем активный промокод пользователя
                    await clear_user_promocode(str(message.from_user.id))
            
            await session.commit()
            
            # Отправляем подтверждение
            keyboard = await get_main_keyboard(str(message.from_user.id))
            confirmation_text = f"✅ <b>Подписка активирована!</b>\n\n"
            confirmation_text += f"📋 <b>Подписка:</b> {plan.name}\n"
            confirmation_text += f"⏰ <b>Срок:</b> {plan.duration_days} дней\n"
            confirmation_text += f"📅 <b>Действует до:</b> {end_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            
            if promo_applied:
                confirmation_text += f"🎟 <b>Промокод применен!</b> Скидка {user_promocode.discount_percent}% учтена.\n\n"
            
            confirmation_text += "Теперь у вас есть доступ ко всем функциям бота!"
            
            await message.answer(
                confirmation_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        print(f"Ошибка при обработке платежа: {e}")
        await message.answer("❌ Ошибка при активации подписки")
