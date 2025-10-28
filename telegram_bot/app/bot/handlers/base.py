"""
Базовые команды бота (start, help)
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from ...db import get_or_create_user, user_has_active_subscription, user_has_ever_had_subscription, create_trial_subscription
from ...db.model import UserSubscription

router = Router()

print("🔍 BASE MODULE: Модуль base.py загружен")


async def get_main_keyboard(telegram_id: str = None):
    print(f"🔍 KEYBOARD: Создаем клавиатуру для пользователя {telegram_id}")
    keyboard_rows = []

    # Проверяем подписку
    has_sub = False
    if telegram_id:
        try:
            print(f"🔍 KEYBOARD: Проверяем подписку для пользователя {telegram_id}")
            has_sub = await user_has_active_subscription(telegram_id)
            print(f"🔍 KEYBOARD: Подписка активна: {has_sub}")
        except Exception as e:
            print(f"❌ KEYBOARD ERROR: Ошибка при проверке подписки: {str(e)}")
            has_sub = False

    if has_sub:
        print(f"🔍 KEYBOARD: Создаем клавиатуру для пользователя с подпиской")
        # Кнопки для пользователей с подпиской
        keyboard_rows.append([KeyboardButton(text="➕ Добавить отслеживание"), KeyboardButton(text="📋 Мои отслеживания")])
    else:
        print(f"🔍 KEYBOARD: Создаем клавиатуру для пользователя без подписки")

        # Кнопки для пользователей без подписки
        keyboard_rows.append([KeyboardButton(text="💳 Купить подписку"), KeyboardButton(text="🎟 Ввести промокод")])

    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True
    )
    print(f"🔍 KEYBOARD: Клавиатура создана с {len(keyboard_rows)} строками")
    return keyboard

@router.message(Command("start"))
async def start_command(message: types.Message):
    print(f"🔍 START HANDLER: Получена команда /start от пользователя {message.from_user.id}")
    
    try:
        print(f"🔍 START HANDLER: Создаем/получаем пользователя {message.from_user.id}")
        # Сохраняем пользователя при первом запуске
        await get_or_create_user(str(message.from_user.id))
        print(f"🔍 START HANDLER: Пользователь создан/получен")
        
        # Проверяем, была ли у пользователя когда-либо подписка
        has_ever_had_subscription = await user_has_ever_had_subscription(str(message.from_user.id))
        
        # Если пользователь никогда не имел подписки, создаем trial подписку
        trial_created = False
        if not has_ever_had_subscription:
            print(f"🔍 START HANDLER: Пользователь {message.from_user.id} никогда не имел подписки, создаем trial")
            trial_created = await create_trial_subscription(str(message.from_user.id))
            if trial_created:
                print(f"✅ START HANDLER: Trial подписка создана для пользователя {message.from_user.id}")
        
        # Проверяем наличие активной подписки
        has_subscription = await user_has_active_subscription(str(message.from_user.id))
        
        print(f"🔍 START HANDLER: Создаем клавиатуру для пользователя {message.from_user.id}")
        keyboard = await get_main_keyboard(str(message.from_user.id))
        print(f"🔍 START HANDLER: Клавиатура создана")
        
        print(f"🔍 START HANDLER: Отправляем приветственное сообщение")
        
        # Формируем сообщение в зависимости от наличия подписки
        if has_subscription:
            # Проверяем, это trial подписка или нет
            if trial_created:
                welcome_text = (
                    "🏠 <b>Gaezy Avito Bot</b>\n\n"
                    "🎉 <b>Добро пожаловать!</b>\n\n"
                    "✅ <b>Вам предоставлен бесплатный trial период на 3 дня!</b>\n\n"
                    "Используйте кнопки меню для работы с ботом."
                )
            else:
                welcome_text = (
                    "🏠 <b>Gaezy Avito Bot</b>\n\n"
                    "✅ <b>У вас есть активная подписка!</b>\n\n"
                    "Используйте кнопки меню для работы с ботом."
                )
        else:
            welcome_text = (
                "🏠 <b>Gaezy Avito Bot</b>\n\n"
                "Я помогу отслеживать изменения цен на Avito!\n\n"
                "Если у вас нет активной подписки — нажмите '💳 Купить подписку'."
            )
        
        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        print(f"🔍 START HANDLER: Сообщение отправлено успешно")
        
    except Exception as e:
        print(f"❌ START HANDLER ERROR: Ошибка при обработке /start: {str(e)}")
        import traceback
        traceback.print_exc()
        
        await message.answer(
            f"❌ Произошла ошибка при запуске бота: {str(e)}\n\nПопробуйте позже.",
            parse_mode="HTML"
        )


@router.message(Command("help"))
async def help_command(message: types.Message):
    """Обработчик команды /help"""
    try:
        help_text = (
            "❓ <b>Помощь по боту Gaezy Avito</b>\n\n"
            "🤖 <b>Основные команды:</b>\n"
            "• /start - Запустить бота\n"
            "• /help - Показать эту справку\n\n"
            "🔍 <b>Возможности бота:</b>\n"
            "• Отслеживание цен на Avito\n"
            "• Уведомления об изменениях\n"
            "• Управление подписками\n\n"
            "📞 <b>Поддержка:</b>\n"
            "По всем вопросам обращайтесь к администратору\n\n"
            "💡 <b>Подсказка:</b>\n"
            "Используйте кнопки меню для навигации"
        )
        
        keyboard = await get_main_keyboard(str(message.from_user.id))
        await message.answer(help_text, parse_mode="HTML", reply_markup=keyboard)
        
    except Exception as e:
        await message.answer("❌ Произошла ошибка при отображении справки")


@router.message(lambda message: message.text == "➕ Добавить отслеживание")
async def add_tracking_menu(message: types.Message):
    """Показать меню добавления отслеживания"""
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
        
    await message.answer(
        "➕ <b>Добавить отслеживание</b>\n\n"
        "🎯 <b>Отслеживание конкретного объявления:</b>\n"
        "Введите ссылку на объявление Avito для отслеживания изменений цены.\n\n"
        "Также можете указать ценовые фильтры в формате:\n"
        "<code>ссылка | мин_цена | макс_цена</code>\n\n"
        "Например:\n"
        "<code>https://www.avito.ru/moskva/telefony/iphone_13_123456789 | 50000 | 80000</code>\n\n"
        "Бот будет отслеживать изменения цены объявления и уведомлять вас при изменениях.",
        parse_mode="HTML"
    )


@router.message(lambda message: message.text == "📋 Мои отслеживания")
async def list_trackings(message: types.Message):
    """Показать список отслеживаний с названиями и номерами"""
    from ...db import get_user_trackings
    
    user_id = str(message.from_user.id)
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(user_id)
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    # Получаем отслеживания (активные и архивированные)
    active_trackings = await get_user_trackings(user_id, active_only=True)
    all_trackings = await get_user_trackings(user_id, active_only=False)
    archived_trackings = [t for t in all_trackings if not t.is_active]
    
    if not all_trackings:
        await message.answer(
            "📋 У вас нет отслеживаний.\n\n"
            "Используйте кнопку '➕ Добавить отслеживание' чтобы начать отслеживать объявления."
        )
        return
    
    response = "📋 <b>Ваши отслеживания</b>\n\n"
    
    if active_trackings:
        response += "🟢 <b>Активные:</b>\n"
        for i, tracking in enumerate(active_trackings, 1):
            name = tracking.name if tracking.name else f"Ссылка {i}"
            response += f"<b>{i}.</b> {name}\n"
            if tracking.min_price and tracking.max_price:
                response += f"   💰 {tracking.min_price} - {tracking.max_price} ₽\n"
            elif tracking.min_price:
                response += f"   💰 от {tracking.min_price} ₽\n"
            elif tracking.max_price:
                response += f"   💰 до {tracking.max_price} ₽\n"
            response += "\n"
    
    if archived_trackings:
        response += "🟡 <b>Архивированные:</b>\n"
        for i, tracking in enumerate(archived_trackings, len(active_trackings) + 1):
            name = tracking.name if tracking.name else f"Ссылка {i}"
            response += f"<b>{i}.</b> {name}\n"
            if tracking.min_price and tracking.max_price:
                response += f"   💰 {tracking.min_price} - {tracking.max_price} ₽\n"
            elif tracking.min_price:
                response += f"   💰 от {tracking.min_price} ₽\n"
            elif tracking.max_price:
                response += f"   💰 до {tracking.max_price} ₽\n"
            response += "\n"
    
    response += "💡 <i>Для редактирования отправьте номер отслеживания</i>"
    
    await message.answer(response, parse_mode="HTML")