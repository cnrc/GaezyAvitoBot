import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Токен вашего Telegram бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Авито API credentials
AVITO_CLIENT_ID = os.getenv('AVITO_CLIENT_ID')
AVITO_CLIENT_SECRET = os.getenv('AVITO_CLIENT_SECRET')
AVITO_ACCESS_TOKEN = os.getenv('AVITO_ACCESS_TOKEN')

# API URLs
AVITO_API_BASE_URL = "https://api.avito.ru"
AVITO_AUTH_URL = f"{AVITO_API_BASE_URL}/token"

# Настройки запросов
REQUEST_TIMEOUT = 30  # секунды
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунды

# Настройки мониторинга
CHECK_INTERVAL = 300  # 5 минут
MAX_ITEMS_PER_USER = 10
PRICE_CHANGE_THRESHOLD = 5  # процент изменения цены для уведомления