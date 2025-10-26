from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from ...db.model import get_or_create_user, user_has_active_subscription, user_has_used_promocode, UserSubscription, user_has_ever_had_subscription, create_trial_subscription

router = Router()

print("🔍 START MODULE: Модуль start.py загружен")

async def get_main_keyboard(telegram_id: str = None):
    print(f"🔍 KEYBOARD: Создаем клавиатуру для пользователя {telegram_id}")
    keyboard_rows = []

    # Кнопки для всех
    common_row = [KeyboardButton(text="❓ Помощь")]

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
        # Полный набор функционала
        keyboard_rows.append([KeyboardButton(text="🔍 Найти объявления"), KeyboardButton(text="📋 Мои отслеживаемые")])
        keyboard_rows.append([KeyboardButton(text="⚙️ Управление")])
    else:
        print(f"🔍 KEYBOARD: Создаем клавиатуру для пользователя без подписки")

        # Кнопки для пользователей без подписки
        keyboard_rows.append([KeyboardButton(text="💳 Купить подписку"), KeyboardButton(text="🎟 Ввести промокод")])

    # Добавляем общую строку
    keyboard_rows.append(common_row)

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