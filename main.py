import logging
import os
import random
from functools import wraps
import asyncio
import io  # Для работы с изображениями
from typing import List

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ReactionTypeEmoji, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import aiofiles  # Асинхронное чтение файлов
import httpx
from mtranslate import translate
from characterai import aiocai

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
CHANNELS: List[List[str]] = [
    ["ХахБот новости", "-1002404360993", "https://t.me/hahbot_news"]
]

NOT_SUB_MESSAGE = (
    "Вы не подписаны на обязательный канал. Пожалуйста, подпишитесь, чтобы использовать бота."
)

# Глобальный список эмодзи для реакций
REACTIONS: List[str] = [
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

# --------------------- ЗАГРУЗКА ПРОМПТОВ ---------------------
# Файл generate_image/prompts.txt должен задавать переменные:
# objects, places, styles, colors, adjectives, elements, improvers
async def load_prompts() -> None:
    async with aiofiles.open('generate_image/prompts.txt', mode='r', encoding='utf-8') as f:
        content = await f.read()
    exec(content, globals())
    logging.info("Промпты успешно загружены.")

# --------------------- ПРОВЕРКА ПОДПИСКИ ---------------------
async def check_sub_channels(channels: List[List[str]], user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на все обязательные каналы.
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
async def generate_character_response(user_prompt: str) -> str:
    """
    Генерирует текстовый ответ через API Character AI.
    Для каждого запроса создаётся новый клиент.
    """
    try:
        client = aiocai.Client(CLIENT_API_KEY)
        me = await client.get_me()
        async with await client.connect() as chat:
            new_chat, _ = await chat.new_chat(CHARACTER_ID, me.id)
            response = await chat.send_message(CHARACTER_ID, new_chat.chat_id, user_prompt)
            return response.text
    except Exception as e:
        logging.error(f"Ошибка генерации ответа через Character AI: {e}")
        return "Извините, произошла ошибка при генерации ответа."

# --------------------- ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ ---------------------
async def generate_image_from_query(query: str) -> bytes:
    """
    Генерирует изображение на основе запроса.
    Запрос переводится на английский, затем из глобальных списков выбираются случайные элементы.
    """
    character_english = translate(query, 'en')
    object_choice = random.choice(objects)
    place_choice = random.choice(places)
    style_choice = random.choice(styles)
    color_choice = random.choice(colors)
    adjective_choice = random.choice(adjectives)
    element_choice = random.choice(elements)
    improver_choice = random.choice(improvers)
    
    prompt = (
        f"{character_english.upper()}, HYPERREALISM, IN THE FOREGROUND, MAIN FOCUS. "
        f"IN THE BACKGROUND, SECONDARY: {object_choice}, {place_choice}, {style_choice}, "
        f"{color_choice}, {adjective_choice}, {element_choice}, {improver_choice}"
    )
    random_seed = random.randint(1, 1000000)
    url = (
        f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
        f"?seed={random_seed}&width=720&height=720&model=turbo&nofeed=true&nologo=true"
    )
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            return response.content
        else:
            raise Exception("Произошла ошибка при генерации изображения")

# --------------------- ОБРАБОТЧИКИ СООБЩЕНИЙ ---------------------
@dp.message()
@subscription_required
async def handle_message(message: types.Message) -> None:
    """
    Обрабатывает входящие сообщения.
    - Если сообщение начинается с "хахбот нарисуй", генерируется изображение.
    - Если чат личный, бот всегда отвечает.
    - В группах бот отвечает с вероятностью 20%, если не содержит слово "хахбот" и не является реплаем,
      иначе – 100%.
    Также с вероятностью 50% добавляется случайная реакция.
    """
    # Добавляем случайную реакцию (50% шанс)
    if random.random() < 0.5:
        reaction_emoji = random.choice(REACTIONS)
        await message.react([ReactionTypeEmoji(emoji=reaction_emoji)], is_big=True)
    
    text_lower = message.text.lower().strip()
    activator = "хахбот нарисуй"
    
    # Если сообщение начинается с "хахбот нарисуй", генерируем изображение
    if text_lower.startswith(activator):
        query = message.text[len(activator):].strip()
        if not query:
            await message.answer("Укажите, что нарисовать.")
            return
        try:
            image_bytes = await generate_image_from_query(query)
            photo = io.BytesIO(image_bytes)
            photo.name = 'generated_image.jpg'
            await message.answer_photo(photo, caption="Сгенерированное изображение:")
        except Exception as e:
            logging.error(f"Ошибка генерации изображения: {e}")
            await message.answer("Ошибка при генерации изображения.")
        return

    # Определение режима ответа в зависимости от типа чата
    chat_type = message.chat.type
    should_respond = False
    if chat_type == "private":
        should_respond = True
    else:
        # В группах:
        # Если сообщение содержит слово "хахбот" или является реплаем, отвечаем 100%
        if "хахбот" in text_lower or message.reply_to_message is not None:
            should_respond = True
        else:
            should_respond = random.random() < 0.2

    if not should_respond:
        return

    # Генерируем текстовый ответ через Character AI
    generated_response = await generate_character_response(message.text)
    await message.answer(generated_response)

@dp.callback_query(lambda c: c.data == "check_sub")
async def process_check_sub(callback_query: types.CallbackQuery) -> None:
    """
    Обрабатывает нажатие кнопки "Проверить" для повторной проверки подписки.
    """
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

# --------------------- ОБРАБОТЧИК ДЛЯ ПУТИ "/" ---------------------
async def handle_root(request: web.Request) -> web.Response:
    logging.info("Получен запрос на корневой путь от %s", request.remote)
    return web.Response(text="OK")

# --------------------- НАСТРОЙКА ВЕБХУКА ---------------------
async def on_startup(app: web.Application) -> None:
    logging.info("Загрузка промптов для генерации изображений...")
    await load_prompts()
    logging.info("Промпты загружены.")
    logging.info("Установка вебхука...")
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Вебхук установлен: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application) -> None:
    logging.info("Удаление вебхука и закрытие сессии...")
    await bot.delete_webhook()
    await bot.session.close()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path='/webhook')
app.router.add_get("/", handle_root)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# --------------------- ТОЧКА ВХОДА ---------------------
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
