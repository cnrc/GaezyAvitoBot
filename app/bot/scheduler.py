import asyncio
from aiogram import Bot
from app.utils.storage import user_items
from app.avito_api import AvitoAPI
from app.config import PRICE_CHANGE_THRESHOLD, CHECK_INTERVAL

api = AvitoAPI()

async def check_prices(bot: Bot):
    # One-shot check over all users (can be scheduled periodically by caller)
    for user_id, items in list(user_items.items()):
        for item_id, last_price in list(items.items()):
            try:
                item_details = await api.get_item_details(item_id)
                if not item_details:
                    del items[item_id]
                    await bot.send_message(chat_id=user_id, text=f"❌ Объявление {item_id} больше не доступно и удалено из отслеживания")
                    continue

                current_price = float(item_details.get('price', 0))
                if current_price != last_price:
                    price_change = ((current_price - last_price) / last_price) * 100 if last_price else 0
                    if abs(price_change) >= PRICE_CHANGE_THRESHOLD:
                        direction = "выросла" if current_price > last_price else "снизилась"
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"🚨 Изменение цены в объявлении!\n"
                                f"ID: {item_id}\n"
                                f"Название: {item_details.get('title','Не указано')}\n"
                                f"Цена {direction} на {abs(price_change):.2f}%\n"
                                f"С {last_price:,.2f} ₽ до {current_price:,.2f} ₽"
                            )
                        )
                        items[item_id] = current_price
            except Exception:
                # Log silently; avito_api has its own logging
                continue
