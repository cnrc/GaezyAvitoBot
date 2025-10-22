from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from ...db.model import get_or_create_user, user_has_active_subscription

router = Router()

async def get_main_keyboard(telegram_id: str = None):
    keyboard_rows = []

    # Кнопки для всех
    common_row = [KeyboardButton(text="❓ Помощь")]

    # Проверяем подписку
    has_sub = False
    if telegram_id:
        try:
            has_sub = await user_has_active_subscription(telegram_id)
        except Exception as e:
            has_sub = False

    if has_sub:
        # Полный набор функционала
        keyboard_rows.append([KeyboardButton(text="🔍 Найти объявления"), KeyboardButton(text="📋 Мои отслеживаемые")])
        keyboard_rows.append([KeyboardButton(text="⚙️ Управление")])
    else:
        # Кнопка покупки подписки
        keyboard_rows.append([KeyboardButton(text="💳 Купить подписку")])

    # Добавляем общую строку
    keyboard_rows.append(common_row)

    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или введите ID..."
    )
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
    try:
        # Сохраняем пользователя при первом запуске
        await get_or_create_user(str(message.from_user.id))
        
        keyboard = await get_main_keyboard(str(message.from_user.id))
        await message.answer(
            "🏠 <b>Avito Price Monitor</b>\n\n"
            "Я помогу отслеживать изменения цен на Avito!\n\n"
            "Если у вас нет активной подписки — нажмите '💳 Купить подписку'.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже.",
            parse_mode="HTML"
        )