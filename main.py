import logging
import os
import random
from functools import wraps

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ReactionTypeEmoji, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# --------------------- Конфигурация ---------------------

API_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
if not API_TOKEN or not WEBHOOK_URL:
    raise ValueError("Необходимо установить переменные окружения BOT_TOKEN и WEBHOOK_URL")

WEBAPP_HOST = '0.0.0.0'
WEBAPP_PORT = int(os.getenv('PORT', 10000))

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Список обязательных каналов в формате: [название, chat_id, URL]
CHANNELS = [
    ["ХахБот новости", "-1002404360993", "https://t.me/hahbot_news"]
]

# Сообщение для пользователей, не подписанных на канал(ы)
NOT_SUB_MESSAGE = (
    "Вы не подписаны на обязательный канал. Пожалуйста, подпишитесь, чтобы использовать бота."
)

# --------------------- Функции проверки подписки ---------------------

async def check_sub_channels(channels: list, user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь (user_id) на все указанные каналы.
    Использует метод get_chat_member для каждого канала.
    """
    for channel in channels:
        channel_id = channel[1]
        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            logging.error(
                f"Ошибка проверки подписки для user_id {user_id} в канале {channel_id}: {e}"
            )
            return False
    return True

def subscription_required(handler):
    """
    Декоратор для проверки подписки пользователя на обязательные каналы.
    Если пользователь не подписан, отправляется сообщение с кнопками для подписки и проверки.
    """
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = message.from_user.id
        if not await check_sub_channels(CHANNELS, user_id):
            # Передаём явно inline_keyboard=[], чтобы не было ошибки валидации
            keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=1)
            for channel in CHANNELS:
                subscribe_button = InlineKeyboardButton(text=channel[0], url=channel[2])
                keyboard.add(subscribe_button)
            check_button = InlineKeyboardButton(text="Проверить", callback_data="check_sub")
            keyboard.add(check_button)
            await message.answer(NOT_SUB_MESSAGE, reply_markup=keyboard)
            return  # Прерываем выполнение основного обработчика
        return await handler(message, *args, **kwargs)
    return wrapper

# --------------------- Обработчики ---------------------

@dp.message()
@subscription_required
async def handle_message(message: types.Message):
    """
    Основной обработчик сообщений.
    Если пользователь подписан на все каналы, с вероятностью 50% бот ставит случайную реакцию.
    """
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
        reaction_obj = ReactionTypeEmoji(emoji=reaction_emoji)
        await message.react([reaction_obj], is_big=True)

@dp.callback_query(lambda c: c.data == "check_sub")
async def process_check_sub(callback_query: types.CallbackQuery):
    """
    Обработчик нажатия кнопки "Проверить".
    Если пользователь теперь подписан, отправляется уведомление об успехе.
    """
    user_id = callback_query.from_user.id
    if await check_sub_channels(CHANNELS, user_id):
        await callback_query.answer("Спасибо, теперь вы подписаны!", show_alert=True)
        # При необходимости можно обновить или удалить сообщение с кнопками
    else:
        await callback_query.answer(
            "Вы все еще не подписаны. Пожалуйста, подпишитесь.", show_alert=True
        )

# --------------------- Функции для работы вебхука ---------------------

async def on_startup(app: web.Application):
    logging.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Вебхук установлен: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application):
    logging.info("Удаление вебхука и закрытие сессии...")
    await bot.delete_webhook()
    await bot.session.close()

# --------------------- Инициализация веб-приложения ---------------------

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path='/webhook')
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# --------------------- Точка входа ---------------------

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
