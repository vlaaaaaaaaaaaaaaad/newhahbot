import logging
import os
import random
from functools import wraps
import aiohttp  # Для асинхронных HTTP запросов

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

# --------------------- ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ОТВЕТА ЧЕРЕЗ CHARACTER AI ---------------------
async def generate_character_response(prompt: str) -> str:
    """
    Генерирует ответ, используя Character AI API.
    Для каждого нового запроса создаётся новый клиент.
    """
    # Предположительный URL – уточните согласно документации https://docs.kram.cat/
    api_url = "https://api.kram.cat/v1/generate"
    headers = {
        "Authorization": f"Bearer {CLIENT_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "character_id": CHARACTER_ID,
        "input": prompt
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Предполагаем, что ответ находится в data["response"]
                    return data.get("response", "Извините, не удалось сгенерировать ответ.")
                else:
                    logging.error(f"Ошибка при вызове Character AI API: статус {resp.status}")
                    return "Извините, произошла ошибка при генерации ответа."
    except Exception as e:
        logging.error(f"Исключение при вызове Character AI API: {e}")
        return "Извините, произошла ошибка при генерации ответа."

# --------------------- ОБРАБОТЧИКИ ---------------------
@dp.message()
@subscription_required
async def handle_message(message: types.Message):
    """
    Основной обработчик сообщений.
    Если пользователь подписан, с вероятностью 50% бот ставит случайную реакцию,
    а также всегда генерирует ответ через Character AI API.
    """
    # Случайная реакция (50% шанс)
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
    
    # Генерация ответа через Character AI API (100% шанс)
    prompt = message.text
    response_text = await generate_character_response(prompt)
    await message.answer(response_text)

@dp.callback_query(lambda c: c.data == "check_sub")
async def process_check_sub(callback_query: types.CallbackQuery):
    """
    Обработчик нажатия кнопки "Проверить".
    Если пользователь подписан, редактирует сообщение бота, заменяя его на приветствие
    и удаляя инлайн-клавиатуру.
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
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# --------------------- ТОЧКА ВХОДА ---------------------
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
