import logging
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

# Получение значений из переменных окружения
API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Проверка наличия необходимых переменных
if not API_TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо установить переменные окружения BOT_TOKEN и WEBHOOK_URL")

# Настройки веб-сервера
WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.getenv('PORT', 10000))

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher()

# Обработчик сообщений: с вероятностью 50% отправляем случайную реакцию
@dp.message()
async def handle_message(message: types.Message):
    if random.random() < 0.5:
        # Список случайных реакций (эмодзи)
        reactions = [
        "👍", "👎", "❤", "🔥", 
        "🥰", "👏", "😁", "🤔",
        "🤯", "😱", "🤬", "😢",
        "🎉", "🤩", "🤮", "💩",
        "🙏", "👌", "🕊", "🤡",
        "🥱", "🥴", "😍", "🐳",
        "❤‍🔥", "🌚", "🌭", "💯",
        "🤣", "⚡", "🍌", "🏆",
        "💔", "🤨", "😐", "🍓",
        "🍾", "💋", "🖕", "😈",
        "😴", "😭", "🤓", "👻",
        "👨‍💻", "👀", "🎃", "🙈",
        "😇", "😨", "🤝", "✍",
        "🤗", "🫡", "🎅", "🎄",
        "☃", "💅", "🤪", "🗿",
        "🆒", "💘", "🙉", "🦄",
        "😘", "💊", "🙊", "😎",
        "👾", "🤷‍♂", "🤷", "🤷‍♀",
        "😡"
    ]
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
# Регистрируем обработчик обновлений по пути /webhook
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path='/webhook')

# Регистрируем функции старта и остановки
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)

