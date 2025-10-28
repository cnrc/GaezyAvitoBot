"""
Базовые команды бота (start, help)
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from ...db.model import get_or_create_user, user_has_active_subscription, UserSubscription, user_has_ever_had_subscription, create_trial_subscription

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
        # Новые кнопки
        keyboard_rows.append([KeyboardButton(text="📋 Мои отслеживания")])
        keyboard_rows.append([KeyboardButton(text="➕ Добавить отслеживание")])
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


def get_management_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗑️ Удалить объявление"), KeyboardButton(text="🔄 Обновить цены")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
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


@router.message(lambda message: message.text == "📋 Мои отслеживания")
async def my_trackings(message: types.Message):
    """Показать активные фильтры пользователя"""
    from app.db import get_user_tracked_searches, get_user_tracked_items
    
    user_id = str(message.from_user.id)
    
    # Получаем фильтры (TrackedSearch)
    tracked_searches = await get_user_tracked_searches(user_id)
    
    if not tracked_searches:
        await message.answer("📋 У вас нет активных фильтров для отслеживания.")
        return
    
    msg = "📋 <b>Ваши активные фильтры:</b>\n\n"
    for i, search in enumerate(tracked_searches, 1):
        msg += f"{i}. "
        
        if search.search_query:
            msg += f"Запрос: {search.search_query}\n"
        if search.category_id:
            msg += f"Категория ID: {search.category_id}\n"
        if search.location_id:
            msg += f"Локация ID: {search.location_id}\n"
        if search.price_from:
            msg += f"Цена от: {search.price_from}\n"
        if search.price_to:
            msg += f"Цена до: {search.price_to}\n"
        
        msg += "\n"
    
    await message.answer(msg, parse_mode="HTML")


@router.message(lambda message: message.text == "➕ Добавить отслеживание")
async def add_tracking_menu(message: types.Message):
    """Показать меню добавления отслеживания"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆔 Отслеживание по ID"), KeyboardButton(text="🔍 Отслеживание по фильтрам")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "➕ <b>Добавить отслеживание</b>\n\n"
        "Выберите тип отслеживания:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(lambda message: message.text == "🆔 Отслеживание по ID")
async def tracking_by_id(message: types.Message):
    """Инициировать отслеживание по ID"""
    await message.answer(
        "🆔 <b>Отслеживание по ID</b>\n\n"
        "Введите ID объявления из ссылки Avito:\n"
        "Например: <code>123456789</code>",
        parse_mode="HTML"
    )


@router.message(lambda message: message.text == "🔍 Отслеживание по фильтрам")
async def tracking_by_filters(message: types.Message):
    """Инициировать отслеживание по фильтрам"""
    await message.answer(
        "🔍 <b>Отслеживание по фильтрам</b>\n\n"
        "Введите параметры поиска в формате:\n"
        "<b>Запрос | Категория | Город | Цена от | Цена до</b>\n\n"
        "Например:\n"
        "<code>iPhone 13 | Электроника | Москва | 50000 | 80000</code>\n\n"
        "Необязательные поля можно пропустить.",
        parse_mode="HTML"
    )


@router.message(lambda message: message.text == "◀️ Назад")
async def back_to_main(message: types.Message):
    """Вернуться в главное меню"""
    keyboard = await get_main_keyboard(str(message.from_user.id))
    await message.answer(
        "🏠 <b>Главное меню</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


