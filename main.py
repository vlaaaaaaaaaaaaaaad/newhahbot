import asyncio
import logging
import os
import random
from functools import wraps

from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (ReactionTypeEmoji, InlineKeyboardButton,
                           InlineKeyboardMarkup)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# --------------------- КОНФИГУРАЦИЯ ---------------------
API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
if not API_TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо установить переменные окружения BOT_TOKEN и WEBHOOK_URL")

# Переменные для Character AI API
CHARACTER_ID = os.getenv("CHARACTER_ID")
CLIENT_API_KEY = os.getenv("CLIENT_API_KEY")
if not CHARACTER_ID or not CLIENT_API_KEY:
    raise ValueError("Необходимо установить переменные окружения CHARACTER_ID и CLIENT_API_KEY")

WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.getenv('PORT', 10000))

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Список обязательных каналов: [название, chat_id, URL]
CHANNELS = [
    ["ХахБот новости", "-1002404360993", "https://t.me/hahbot_news"]
]

# Сообщение для пользователей, не подписанных на каналы
NOT_SUB_MESSAGE = (
    "Вы не подписаны на обязательный канал. Пожалуйста, подпишитесь, чтобы использовать бота."
)

# --------------------- ФУНКЦИИ ДЛЯ ПРОВЕРКИ ПОДПИСКИ ---------------------
async def check_sub_channels(channels: list, user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь (user_id) на все указанные каналы.
    Возвращает True, если подписан на все каналы, иначе False.
    """
    for channel in channels:
        channel_id = channel[1]
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            logging.error(f"Ошибка проверки подписки для user_id {user_id} в канале {channel_id}: {e}")
            return False
    return True

def subscription_required(handler):
    """
    Декоратор для проверки подписки пользователя.
    Если пользователь не подписан, отправляется сообщение с кнопками для подписки и проверки,
    а выполнение основного обработчика прерывается.
    """
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        if not await check_sub_channels(CHANNELS, message.from_user.id):
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=channel[0], url=channel[2])]
                    for channel in CHANNELS
                ] + [[InlineKeyboardButton(text="Проверить", callback_data="check_sub")]]
            )
            await message.answer(NOT_SUB_MESSAGE, reply_markup=keyboard)
            return
        return await handler(message, *args, **kwargs)
    return wrapper

# --------------------- ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ ОТВЕТА ---------------------
async def generate_character_ai_response(user_message: str) -> str:
    """
    Генерирует ответ с помощью Character AI API.

    Для каждого нового запроса создаётся новый клиент, устанавливается соединение,
    начинается новый чат и отправляется сообщение пользователя.

    :param user_message: Текст сообщения от пользователя.
    :return: Сгенерированный текст ответа или пустую строку в случае ошибки.
    """
    from characterai import aiocai  # Импорт асинхронного клиента CharacterAI
    try:
        client = aiocai.Client(CLIENT_API_KEY)
        me = await client.get_me()
        async with await client.connect() as chat:
            new_chat, greeting = await chat.new_chat(CHARACTER_ID, me.id)
            response = await chat.send_message(CHARACTER_ID, new_chat.chat_id, user_message)
            return response.text
    except Exception as e:
        logging.error(f"Ошибка при генерации ответа через Character AI API: {e}")
        return ""

# --------------------- ОБРАБОТЧИКИ ---------------------
@dp.message()
@subscription_required
async def handle_message(message: types.Message):
    """
    Основной обработчик текстовых сообщений.
    Генерируется ответ через Character AI API и отправляется в Telegram.
    Дополнительно, с вероятностью 50% отправляется реакция (эмодзи).
    """
    response_text = await generate_character_ai_response(message.text)
    if response_text:
        await message.answer(response_text)
    else:
        await message.answer("Произошла ошибка при генерации ответа. Попробуйте позже.")
    
    # Дополнительная реакция с вероятностью 50%
    if random.random() < 0.5:
        reactions = [
            "👍", "👎", "❤", "🔥", "🥰", "👏", "😁", "🤔",
            "🤯", "😱", "🤬", "😢", "🎉", "🤩", "🤮", "💩",
            "🙏", "👌", "🕊", "🤡", "🥱", "🥴", "😍", "🐳",
            "❤‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆",
            "💔", "🤨", "😐", "🍓", "🍾", "💋", "🖕", "😈",
            "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈",
            "😇", "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄",
            "☃", "💅", "🤪", "🗿", "🆒", "💘", "🙉", "🦄",
            "😘", "💊", "🙊", "😎", "👾", "🤷‍♂", "🤷", "🤷‍♀",
            "😡"
        ]
        reaction = random.choice(reactions)
        try:
            await message.react([ReactionTypeEmoji(emoji=reaction)], is_big=True)
        except Exception as e:
            logging.error(f"Ошибка при отправке реакции: {e}")

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def process_check_sub(callback_query: types.CallbackQuery):
    """
    Обработчик кнопки "Проверить".
    Если пользователь подписан, редактирует сообщение бота, заменяя его на приветствие и удаляя инлайн-клавиатуру.
    """
    if await check_sub_channels(CHANNELS, callback_query.from_user.id):
        welcome_text = "Добро пожаловать! Вы успешно подписались на обязательные каналы."
        await bot.edit_message_text(
            text=welcome_text,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=None  # Удаляем клавиатуру
        )
        await callback_query.answer()  # Скрываем "часики"
    else:
        await callback_query.answer("Вы все еще не подписаны. Пожалуйста, подпишитесь.", show_alert=True)

# --------------------- ДОПОЛНИТЕЛЬНЫЙ МАРШРУТ /check ---------------------
async def check_handler(request: web.Request) -> web.Response:
    """
    Обработчик пути /check.
    Возвращает "OK" для поддержания активности сервера.
    """
    return web.Response(text="OK")

# --------------------- ФОНОВАЯ ЗАДАЧА KEEP-ALIVE ---------------------
async def keep_alive():
    """
    Периодически отправляет GET-запрос к маршруту /check, чтобы сервер не переходил в спящий режим.
    """
    await asyncio.sleep(5)  # небольшая задержка при старте
    while True:
        try:
            async with ClientSession() as session:
                # Используем localhost и порт сервера
                async with session.get(f"http://localhost:{WEBAPP_PORT}/check") as resp:
                    await resp.text()
        except Exception as e:
            logging.error(f"Ошибка в keep_alive: {e}")
        await asyncio.sleep(240)  # каждые 4 минуты

# --------------------- НАСТРОЙКА ВЕБХУКА ---------------------
async def on_startup(app: web.Application):
    logging.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Вебхук установлен: {WEBHOOK_URL}")
    # Добавляем маршрут /check
    app.router.add_get("/check", check_handler)
    # Запускаем фоновую задачу keep_alive
    app['keep_alive'] = asyncio.create_task(keep_alive())

async def on_shutdown(app: web.Application):
    logging.info("Удаление вебхука и закрытие сессии...")
    await bot.delete_webhook()
    try:
        await bot.session.close()
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            logging.warning("Event loop is closed при закрытии сессии, пропускаем.")
        else:
            raise e
    # Отменяем задачу keep_alive
    if 'keep_alive' in app:
        app['keep_alive'].cancel()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path='/webhook')
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# --------------------- ТОЧКА ВХОДА ---------------------
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
