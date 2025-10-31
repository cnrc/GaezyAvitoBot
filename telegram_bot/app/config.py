import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Токен вашего Telegram бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

DATABASE_URL = os.getenv('DATABASE_URL')

YOOKASSA_TOKEN = os.getenv('YOOKASSA_TOKEN')

API_TOKEN = os.getenv('API_TOKEN')

# API парсинга
PARSER_API_URL = os.getenv('PARSER_API_URL')
PARSER_API_TOKEN = os.getenv('PARSER_API_TOKEN')