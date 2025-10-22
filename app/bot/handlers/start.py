from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

router = Router()

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти объявления"), KeyboardButton(text="📋 Мои отслеживаемые")],
            [KeyboardButton(text="⚙️ Управление"), KeyboardButton(text="❓ Помощь")],
            [KeyboardButton(text="📊 Статистика")]
        ],
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
    await message.answer(
        "🏠 <b>Avito Price Monitor</b>\n\n"
        "Я помогу отслеживать изменения цен на Avito!\n\n"
        "<b>Быстрые действия:</b>\n"
        "• Отправьте ID объявления для отслеживания\n"
        "• Используйте кнопки ниже для управления\n\n"
        "<i>ID можно найти в ссылке объявления</i>",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

@router.message(lambda message: message.text == "🔍 Найти объявления")
async def search_ads(message: types.Message):
    await message.answer(
        "🔍 <b>Поиск объявлений</b>\n\n"
        "Введите параметры поиска в формате:\n"
        "Запрос | Категория | Город | Цена от | Цена до\n\n"
        "Например:\n"
        "iPhone 13 | Электроника | Москва | 50000 | 80000\n\n"
        "Или просто введите поисковый запрос", parse_mode="HTML"
        )

@router.message(lambda message: message.text == "📋 Мои отслеживаемые")
async def my_ads(message: types.Message):
    await message.answer("📋 <b>Ваши отслеживаемые объявления:</b>\n\nПока нет отслеживаемых объявлений", parse_mode="HTML")

@router.message(lambda message: message.text == "⚙️ Управление")
async def management(message: types.Message):
    await message.answer("⚙️ <b>Управление отслеживанием</b>", reply_markup=get_management_keyboard(), parse_mode="HTML")

@router.message(lambda message: message.text == "🗑️ Удалить объявление")
async def remove_ad(message: types.Message):
    await message.answer("🗑️ Введите ID объявления для удаления:")

@router.message(lambda message: message.text == "◀️ Назад")
async def back_to_main(message: types.Message):
    await message.answer("Возвращаемся в главное меню:", reply_markup=get_main_keyboard())

@router.message(lambda message: message.text == "❓ Помощь")
async def help_info(message: types.Message):
    await message.answer(
        "❓ <b>Помощь по использованию</b>\n\n"
        "<b>Как отслеживать объявления:</b>\n"
        "1. Найдите объявление на Avito\n"
        "2. Скопируйте ID из ссылки\n"
        "3. Отправьте ID боту\n\n"
        "<b>Пример:</b>\n"
        "<code>123456789</code>\n\n"
        "<b>Поиск объявлений:</b>\n"
        "Нажмите '🔍 Найти объявления' и введите запрос",
        parse_mode="HTML"
    )

# Обработка ID объявлений
@router.message(lambda message: message.text.isdigit())
async def handle_ad_id(message: types.Message):
    ad_id = message.text
    await message.answer(f"✅ <b>Начинаю отслеживание!</b>\n\nID: <code>{ad_id}</code>", parse_mode="HTML")

# Обработка текстовых запросов (поиск)
@router.message()
async def handle_text(message: types.Message):
    if message.text not in ["🔍 Найти объявления", "📋 Мои отслеживаемые", "⚙️ Управление", 
                           "❓ Помощь", "🗑️ Удалить объявление", "◀️ Назад", "📊 Статистика",
                           "🔄 Обновить цены"]:
        await message.answer(f"🔍 <b>Ищу объявления:</b>\n<code>{message.text}</code>", parse_mode="HTML")