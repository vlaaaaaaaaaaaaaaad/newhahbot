import logging
import os
import random
from functools import wraps
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ReactionTypeEmoji, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# --------------------- КОНФИГУРАЦИЯ ---------------------
API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
if not API_TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо установить переменные окружения BOT_TOKEN и WEBHOOK_URL")

# Переменные для Character AI
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

# --------------------- ГЕНЕРАЦИЯ ОТВЕТА ЧЕРЕЗ CHARACTER AI ---------------------
from characterai import aiocai

async def generate_character_response(user_prompt: str) -> str:
    try:
        # Для каждого запроса создаем нового клиента
        client = aiocai.Client(CLIENT_API_KEY)
        me = await client.get_me()
        async with await client.connect() as chat:
            # Запускаем новый чат с указанным CHARACTER_ID
            new_chat, initial_answer = await chat.new_chat(CHARACTER_ID, me.id)
            # Отправляем сообщение пользователя как запрос
            response = await chat.send_message(CHARACTER_ID, new_chat.chat_id, user_prompt)
            return response.text
    except Exception as e:
        logging.error(f"Ошибка генерации ответа через Character AI: {e}")
        return "Извините, произошла ошибка при генерации ответа."

# --------------------- ОБРАБОТЧИКИ ---------------------
@dp.message()
@subscription_required
async def handle_message(message: types.Message):
    # С вероятностью 50% ставим реакцию
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
        reaction_emoji = random.choice(reactions)
        await message.react([ReactionTypeEmoji(emoji=reaction_emoji)], is_big=True)
    
    # Генерация ответа через Character AI (100% шанс)
    generated_response = await generate_character_response(message.text)
    await message.answer(generated_response)

@dp.callback_query(lambda c: c.data == "check_sub")
async def process_check_sub(callback_query: types.CallbackQuery):
    if await check_sub_channels(CHANNELS, callback_query.from_user.id):
        welcome_text = "Добро пожаловать! Вы успешно подписались на обязательные каналы."
        await bot.edit_message_text(
            text=welcome_text,
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=None
        )
        await callback_query.answer()
    else:
        await callback_query.answer("Вы все еще не подписаны. Пожалуйста, подпишитесь.", show_alert=True)

# --------------------- ДОБАВЛЕНИЕ ОБРАБОТЧИКА ДЛЯ ПУТИ "/" ---------------------
async def handle_root(request: web.Request):
    logging.info("Получен запрос на корневой путь от %s", request.remote)
    return web.Response(text="OK")

# --------------------- НАСТРОЙКА ВЕБХУКА ---------------------
async def on_startup(app: web.Application):
    logging.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Вебхук установлен: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application):
    logging.info("Удаление вебхука и закрытие сессии...")
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path='/webhook')
# Регистрируем обработчик для GET-запросов на путь "/"
app.router.add_get("/", handle_root)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# --------------------- ТОЧКА ВХОДА ---------------------
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
