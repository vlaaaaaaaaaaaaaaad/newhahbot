import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

# Замените 'YOUR_BOT_TOKEN' на токен вашего бота
API_TOKEN = 'YOUR_BOT_TOKEN'

# Настройки вебхука
WEBHOOK_HOST = 'https://your.domain.com'  # ваш публичный домен с HTTPS
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Настройки веб-сервера (локальный адрес и порт)
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = 3000

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher()

# Обработчик сообщений: с вероятностью 50% отправляем случайную реакцию
@dp.message()
async def handle_message(message: types.Message):
    if random.random() < 0.5:
        # Список случайных реакций (эмодзи)
        reactions = ['😀', '😂', '😎', '👍', '🙌']
        reaction = random.choice(reactions)
        await message.reply(reaction)

# Функция, вызываемая при старте веб-приложения: устанавливаем вебхук
async def on_startup(app: web.Application):
    logging.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Вебхук установлен: {WEBHOOK_URL}")

# Функция, вызываемая при остановке веб-приложения: удаляем вебхук и закрываем сессию
async def on_shutdown(app: web.Application):
    logging.info("Удаление вебхука...")
    await bot.delete_webhook()
    await bot.session.close()

# Создаем веб-приложение на базе aiohttp
app = web.Application()
# Регистрируем обработчик обновлений по пути WEBHOOK_PATH
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

# Регистрируем функции старта и остановки
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
