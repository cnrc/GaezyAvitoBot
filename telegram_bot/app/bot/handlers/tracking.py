"""
Обработчики для отслеживания объявлений Avito
"""
import re
from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.db import user_has_active_subscription, add_tracking, archive_tracking, restore_tracking, delete_tracking, get_user_trackings

router = Router()

print("🔍 TRACKING MODULE: Модуль tracking.py загружен")

# Состояния для добавления отслеживания
tracking_states = {}  # user_id: {"state": "waiting_name", "link": "...", "min_price": ..., "max_price": ...}



# Обработчик кнопки "➕ Добавить отслеживание" находится в base.py


# Обработчик кнопки "⚙️ Управлять отслеживаниями" находится в base.py


@router.message(lambda message: message.text and message.text.startswith("/test_tracking"))
async def test_tracking_handler(message: types.Message):
    """Тест обработчика отслеживания для диагностики"""
    print(f"🔍 TEST TRACKING: Тестовая команда получена от пользователя {message.from_user.id}")
    await message.answer("✅ Обработчик отслеживания работает! Попробуйте отправить ссылку на Avito.")


@router.message(lambda message: message.text and message.text.startswith("/debug_tracking"))
async def debug_tracking(message: types.Message):
    """Отладочный обработчик для проверки функции отслеживания"""
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    # Пробуем добавить тестовое отслеживание
    try:
        success = await add_tracking(
            telegram_id=str(message.from_user.id),
            link="https://www.avito.ru/test/test/test_123456789",
            min_price=1000,
            max_price=5000
        )
        
        if success:
            await message.answer("✅ Тестовое отслеживание добавлено успешно!")
        else:
            await message.answer("❌ Ошибка при добавлении тестового отслеживания.")
            
    except Exception as e:
        await message.answer(f"❌ Исключение: {str(e)}")
        print(f"Debug error: {e}")
        import traceback
        traceback.print_exc()


@router.message(lambda message: message.text and "avito.ru" in message.text.lower())
async def handle_add_tracking_link(message: types.Message):
    """Обработчик добавления отслеживания по ссылке Avito"""
    print(f"🔍 TRACKING: Добавляем отслеживание для пользователя {message.from_user.id}")
    print(f"🔍 TRACKING: Ссылка: {message.text}")
    
    # Проверяем активную подписку
    print(f"🔍 TRACKING HANDLER: Проверяем активную подписку для пользователя {message.from_user.id}")
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    print(f"🔍 TRACKING HANDLER: Активная подписка: {has_sub}")
    
    if not has_sub:
        print(f"🔍 TRACKING HANDLER: Пользователь {message.from_user.id} не имеет активной подписки")
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    text = message.text.strip()
    print(f"🔍 TRACKING HANDLER: Обрабатываем текст: '{text}'")
    
    # Обработка формата "ссылка | мин_цена | макс_цена"
    if "|" in text:
        parts = [p.strip() for p in text.split("|")]
        link = parts[0] if parts[0] else None
        min_price = None
        max_price = None
        
        if len(parts) > 1 and parts[1].isdigit():
            min_price = int(parts[1])
        if len(parts) > 2 and parts[2].isdigit():
            max_price = int(parts[2])
    else:
        # Простая ссылка без фильтров
        link = text
        min_price = None
        max_price = None
    
    # Очищаем ссылку от лишних символов (например, @ в начале)
    if link:
        link = link.lstrip('@').strip()
    
    # Проверяем, что это действительно ссылка на Avito
    if not link or "avito.ru" not in link.lower():
        await message.answer("❌ Это не ссылка на Avito.")
        return
    
    # Простая валидация - проверяем только наличие avito.ru в ссылке
    if not link.startswith(('http://', 'https://')):
        await message.answer(
            "❌ Пожалуйста, укажите полную ссылку на объявление Avito.\n\n"
            "Ссылка должна начинаться с http:// или https://",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем данные и запрашиваем название
    user_id = message.from_user.id
    tracking_states[user_id] = {
        "state": "waiting_name",
        "link": link,
        "min_price": min_price,
        "max_price": max_price
    }
    
    # Создаем клавиатуру с кнопкой "Без названия"
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏷 Без названия")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "🏷 <b>Название отслеживания</b>\n\n"
        "Дайте название этому отслеживанию для удобства управления.\n\n"
        f"📎 Ссылка: <code>{link[:50]}{'...' if len(link) > 50 else ''}</code>\n\n"
        "💬 Введите название или нажмите кнопку:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(lambda message: message.text == "🏷 Без названия")
async def handle_no_name_tracking(message: types.Message):
    """Обработчик кнопки 'Без названия'"""
    user_id = message.from_user.id
    
    if user_id not in tracking_states or tracking_states[user_id]["state"] != "waiting_name":
        return
    
    await complete_tracking_addition(message, name=None)


@router.message(lambda message: message.text == "❌ Отменить" and message.from_user.id in tracking_states)
async def handle_cancel_tracking(message: types.Message):
    """Обработчик кнопки отмены"""
    user_id = message.from_user.id
    
    if user_id in tracking_states:
        del tracking_states[user_id]
    
    # Возвращаем основную клавиатуру
    from ..handlers.base import get_main_keyboard
    keyboard = await get_main_keyboard(str(message.from_user.id))
    
    await message.answer(
        "❌ Добавление отслеживания отменено.",
        reply_markup=keyboard
    )


@router.message(lambda message: message.from_user.id in tracking_states and tracking_states[message.from_user.id]["state"] == "waiting_name")
async def handle_tracking_name_input(message: types.Message):
    """Обработчик ввода названия отслеживания"""
    user_id = message.from_user.id
    
    if not message.text or message.text.startswith(('/start', '/help', '/admin')):
        return  # Пропускаем команды
    
    name = message.text.strip()
    if len(name) > 100:  # Ограничиваем длину названия
        await message.answer("❌ Название слишком длинное. Максимум 100 символов.")
        return
    
    await complete_tracking_addition(message, name=name)


async def complete_tracking_addition(message: types.Message, name: str = None):
    """Завершает добавление отслеживания"""
    user_id = message.from_user.id
    
    if user_id not in tracking_states:
        return
    
    state_data = tracking_states[user_id]
    del tracking_states[user_id]  # Очищаем состояние
    
    try:
        success = await add_tracking(
            telegram_id=str(user_id),
            link=state_data["link"],
            name=name,
            min_price=state_data["min_price"],
            max_price=state_data["max_price"]
        )
        
        if success:
            msg = "✅ <b>Отслеживание добавлено!</b>\n\n"
            if name:
                msg += f"🏷 Название: <b>{name}</b>\n"
            msg += f"📎 Ссылка: {state_data['link'][:50]}{'...' if len(state_data['link']) > 50 else ''}\n"
            
            if state_data["min_price"] and state_data["max_price"]:
                msg += f"💰 Ценовой диапазон: {state_data['min_price']} - {state_data['max_price']} ₽\n"
            elif state_data["min_price"]:
                msg += f"💰 Цена от: {state_data['min_price']} ₽\n"
            elif state_data["max_price"]:
                msg += f"💰 Цена до: {state_data['max_price']} ₽\n"
            
            msg += "\nБот будет отслеживать изменения цены и уведомлять вас."
        else:
            msg = "❌ Ошибка при добавлении отслеживания. Попробуйте позже."
        
        # Возвращаем основную клавиатуру
        from ..handlers.base import get_main_keyboard
        keyboard = await get_main_keyboard(str(message.from_user.id))
        
        await message.answer(msg, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"❌ Ошибка при завершении добавления отслеживания: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


# Обработчик номеров отслеживаний
@router.message(lambda message: message.text and message.text.isdigit())
async def handle_tracking_number(message: types.Message):
    """Обработчик номеров отслеживаний для управления"""
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        return  # Пропускаем если нет подписки
    
    try:
        number = int(message.text.strip())
        if number < 1:
            return
        
        user_id = str(message.from_user.id)
        
        # Получаем все отслеживания пользователя
        active_trackings = await get_user_trackings(user_id, active_only=True)
        all_trackings = await get_user_trackings(user_id, active_only=False)
        archived_trackings = [t for t in all_trackings if not t.is_active]
        
        # Объединяем списки (сначала активные, потом архивированные)
        all_trackings_ordered = active_trackings + archived_trackings
        
        if number > len(all_trackings_ordered):
            await message.answer(f"❌ Отслеживание с номером {number} не найдено.")
            return
        
        # Получаем выбранное отслеживание
        selected_tracking = all_trackings_ordered[number - 1]
        
        # Определяем статус
        is_active = selected_tracking.is_active
        status_text = "🟢 Активное" if is_active else "🟡 Архивировано"
        name = selected_tracking.name if selected_tracking.name else f"Ссылка {number}"
        
        # Создаем клавиатуру с действиями
        keyboard_buttons = []
        
        if is_active:
            keyboard_buttons.append([InlineKeyboardButton(text="🗂️ Архивировать", callback_data=f"archive_track:{selected_tracking.id}")])
        else:
            keyboard_buttons.append([InlineKeyboardButton(text="🔄 Восстановить", callback_data=f"restore_track:{selected_tracking.id}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_track:{selected_tracking.id}")])
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_track_action")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        # Формируем сообщение
        msg = f"✏️ <b>Редактирование отслеживания #{number}</b>\n\n"
        msg += f"🏷 <b>Название:</b> {name}\n"
        msg += f"📊 <b>Статус:</b> {status_text}\n"
        
        if selected_tracking.min_price and selected_tracking.max_price:
            msg += f"💰 <b>Цена:</b> {selected_tracking.min_price} - {selected_tracking.max_price} ₽\n"
        elif selected_tracking.min_price:
            msg += f"💰 <b>Цена от:</b> {selected_tracking.min_price} ₽\n"
        elif selected_tracking.max_price:
            msg += f"💰 <b>Цена до:</b> {selected_tracking.max_price} ₽\n"
        
        msg += f"📎 <b>Ссылка:</b> {selected_tracking.link[:50]}{'...' if len(selected_tracking.link) > 50 else ''}\n\n"
        msg += "Выберите действие:"
        
        await message.answer(msg, reply_markup=keyboard, parse_mode="HTML")
        
    except ValueError:
        return  # Не число, пропускаем
    except Exception as e:
        print(f"❌ Ошибка при обработке номера отслеживания: {e}")
        import traceback
        traceback.print_exc()


# Callback обработчики для новых inline кнопок
@router.callback_query(lambda callback: callback.data.startswith("archive_track:"))
async def callback_archive_track(callback: types.CallbackQuery):
    """Callback обработчик архивирования отслеживания"""
    tracking_id = callback.data.split(":", 1)[1]
    
    try:
        success = await archive_tracking(
            telegram_id=str(callback.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await callback.message.edit_text("🗂️ ✅ Отслеживание заархивировано.")
        else:
            await callback.message.edit_text("❌ Отслеживание не найдено или уже заархивировано.")
            
        await callback.answer()
        
    except Exception as e:
        print(f"Ошибка при архивировании отслеживания: {e}")
        await callback.message.edit_text("❌ Ошибка при архивировании.")
        await callback.answer()


@router.callback_query(lambda callback: callback.data.startswith("restore_track:"))
async def callback_restore_track(callback: types.CallbackQuery):
    """Callback обработчик восстановления отслеживания"""
    tracking_id = callback.data.split(":", 1)[1]
    
    try:
        success = await restore_tracking(
            telegram_id=str(callback.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await callback.message.edit_text("🔄 ✅ Отслеживание восстановлено.")
        else:
            await callback.message.edit_text("❌ Отслеживание не найдено.")
            
        await callback.answer()
        
    except Exception as e:
        print(f"Ошибка при восстановлении отслеживания: {e}")
        await callback.message.edit_text("❌ Ошибка при восстановлении.")
        await callback.answer()


@router.callback_query(lambda callback: callback.data.startswith("delete_track:"))
async def callback_delete_track(callback: types.CallbackQuery):
    """Callback обработчик удаления отслеживания"""
    tracking_id = callback.data.split(":", 1)[1]
    
    try:
        success = await delete_tracking(
            telegram_id=str(callback.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await callback.message.edit_text("🗑️ ✅ Отслеживание удалено.")
        else:
            await callback.message.edit_text("❌ Отслеживание не найдено.")
            
        await callback.answer()
        
    except Exception as e:
        print(f"Ошибка при удалении отслеживания: {e}")
        await callback.message.edit_text("❌ Ошибка при удалении.")
        await callback.answer()


@router.callback_query(lambda callback: callback.data == "cancel_track_action")
async def callback_cancel_track_action(callback: types.CallbackQuery):
    """Callback обработчик отмены действия"""
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()


@router.message(lambda message: message.text and message.text.startswith("archive:"))
async def handle_archive_tracking(message: types.Message):
    """Обработчик архивирования отслеживания по команде archive:ID"""
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    try:
        tracking_id = message.text.split(":", 1)[1].strip()
        
        if not tracking_id:
            await message.answer("❌ Укажите ID отслеживания после 'archive:'")
            return
        
        success = await archive_tracking(
            telegram_id=str(message.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await message.answer("✅ Отслеживание заархивировано.")
        else:
            await message.answer("❌ Отслеживание не найдено или уже заархивировано.")
            
    except Exception as e:
        print(f"Ошибка при архивировании отслеживания: {e}")
        await message.answer("❌ Ошибка при архивировании. Попробуйте позже.")


@router.message(lambda message: message.text and message.text.startswith("delete:"))
async def handle_delete_tracking(message: types.Message):
    """Обработчик удаления отслеживания по команде delete:ID"""
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    try:
        tracking_id = message.text.split(":", 1)[1].strip()
        
        if not tracking_id:
            await message.answer("❌ Укажите ID отслеживания после 'delete:'")
            return
        
        success = await delete_tracking(
            telegram_id=str(message.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await message.answer("✅ Отслеживание удалено.")
        else:
            await message.answer("❌ Отслеживание не найдено.")
            
    except Exception as e:
        print(f"Ошибка при удалении отслеживания: {e}")
        await message.answer("❌ Ошибка при удалении. Попробуйте позже.")


# Обработчик для UUID (когда пользователь просто вставляет ID)
@router.message(lambda message: message.text and re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', message.text.strip()))
async def handle_uuid_input(message: types.Message):
    """Обработчик UUID для управления отслеживаниями"""
    
    # Проверяем активную подписку
    has_sub = await user_has_active_subscription(str(message.from_user.id))
    if not has_sub:
        await message.answer("⛔ Доступно только с активной подпиской.")
        return
    
    tracking_id = message.text.strip()
    
    # Создаем inline клавиатуру для выбора действия
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗂️ Архивировать", callback_data=f"archive_tracking:{tracking_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_tracking:{tracking_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
        ]
    )
    
    await message.answer(
        f"🆔 <b>ID отслеживания:</b> <code>{tracking_id}</code>\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# Callback обработчики для inline кнопок
@router.callback_query(lambda callback: callback.data.startswith("archive_tracking:"))
async def callback_archive_tracking(callback: types.CallbackQuery):
    """Callback обработчик архивирования отслеживания"""
    tracking_id = callback.data.split(":", 1)[1]
    
    try:
        success = await archive_tracking(
            telegram_id=str(callback.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await callback.message.edit_text("✅ Отслеживание заархивировано.")
        else:
            await callback.message.edit_text("❌ Отслеживание не найдено или уже заархивировано.")
            
        await callback.answer()
        
    except Exception as e:
        print(f"Ошибка при архивировании отслеживания: {e}")
        await callback.message.edit_text("❌ Ошибка при архивировании.")
        await callback.answer()


@router.callback_query(lambda callback: callback.data.startswith("delete_tracking:"))
async def callback_delete_tracking(callback: types.CallbackQuery):
    """Callback обработчик удаления отслеживания"""
    tracking_id = callback.data.split(":", 1)[1]
    
    try:
        success = await delete_tracking(
            telegram_id=str(callback.from_user.id),
            tracking_id=tracking_id
        )
        
        if success:
            await callback.message.edit_text("✅ Отслеживание удалено.")
        else:
            await callback.message.edit_text("❌ Отслеживание не найдено.")
            
        await callback.answer()
        
    except Exception as e:
        print(f"Ошибка при удалении отслеживания: {e}")
        await callback.message.edit_text("❌ Ошибка при удалении.")
        await callback.answer()


@router.callback_query(lambda callback: callback.data == "cancel_action")
async def callback_cancel_action(callback: types.CallbackQuery):
    """Callback обработчик отмены действия"""
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()


# Обработчик кнопки "🏷 Без названия"
@router.message(lambda message: message.text == "🏷 Без названия")
async def handle_no_name_tracking(message: types.Message):
    """Обработчик кнопки 'Без названия'"""
    user_id = message.from_user.id
    
    if user_id not in tracking_states or tracking_states[user_id]["state"] != "waiting_name":
        return
    
    await complete_tracking_addition(message, name=None)


# Обработчик кнопки отмены
@router.message(lambda message: message.text == "❌ Отменить" and message.from_user.id in tracking_states)
async def handle_cancel_tracking(message: types.Message):
    """Обработчик кнопки отмены"""
    user_id = message.from_user.id
    
    if user_id in tracking_states:
        del tracking_states[user_id]
    
    # Возвращаем основную клавиатуру
    from ..handlers.base import get_main_keyboard
    keyboard = await get_main_keyboard(str(message.from_user.id))
    
    await message.answer(
        "❌ Добавление отслеживания отменено.",
        reply_markup=keyboard
    )


# Обработчик ввода названия отслеживания
@router.message(lambda message: message.from_user.id in tracking_states and tracking_states[message.from_user.id]["state"] == "waiting_name" and message.text and not message.text.startswith("/"))
async def handle_tracking_name_input(message: types.Message):
    """Обработчик ввода названия отслеживания"""
    user_id = message.from_user.id
    
    name = message.text.strip()
    if len(name) > 100:  # Ограничиваем длину названия
        await message.answer("❌ Название слишком длинное. Максимум 100 символов.")
        return
    
    await complete_tracking_addition(message, name=name)


async def complete_tracking_addition(message: types.Message, name: str = None):
    """Завершает добавление отслеживания"""
    user_id = message.from_user.id
    
    if user_id not in tracking_states:
        return
    
    state_data = tracking_states[user_id]
    del tracking_states[user_id]  # Очищаем состояние
    
    try:
        success = await add_tracking(
            telegram_id=str(user_id),
            link=state_data["link"],
            name=name,
            min_price=state_data["min_price"],
            max_price=state_data["max_price"]
        )
        
        if success:
            msg = "✅ <b>Отслеживание добавлено!</b>\n\n"
            if name:
                msg += f"🏷 Название: <b>{name}</b>\n"
            msg += f"📎 Ссылка: {state_data['link'][:50]}{'...' if len(state_data['link']) > 50 else ''}\n"
            
            if state_data["min_price"] and state_data["max_price"]:
                msg += f"💰 Ценовой диапазон: {state_data['min_price']} - {state_data['max_price']} ₽\n"
            elif state_data["min_price"]:
                msg += f"💰 Цена от: {state_data['min_price']} ₽\n"
            elif state_data["max_price"]:
                msg += f"💰 Цена до: {state_data['max_price']} ₽\n"
            
            msg += "\nБот будет отслеживать изменения цены и уведомлять вас."
        else:
            msg = "❌ Ошибка при добавлении отслеживания. Попробуйте позже."
        
        # Возвращаем основную клавиатуру
        from ..handlers.base import get_main_keyboard
        keyboard = await get_main_keyboard(str(message.from_user.id))
        
        await message.answer(msg, reply_markup=keyboard, parse_mode="HTML")
        
    except Exception as e:
        print(f"❌ Ошибка при завершении добавления отслеживания: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
