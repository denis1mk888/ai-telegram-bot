# ai_bot.py — Telegram AI-бот с интеграцией YandexGPT
#
# Stack: aiogram 3.x, OpenAI SDK (совместимый клиент для YandexGPT)
# Возможности: диалог с AI, память контекста на пользователя, команда сброса истории
#
# Перед запуском:
#   pip install aiogram openai
#   Заполнить BOT_TOKEN и YANDEX_API_KEY ниже (или через переменные окружения)

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")          # @BotFather
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "YOUR_YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "YOUR_FOLDER_ID")
MODEL_NAME = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite"

SYSTEM_PROMPT = (
    "Ты — дружелюбный AI-ассистент в Telegram-боте. "
    "Отвечай кратко, понятно и по делу. "
    "Если не знаешь точного ответа — честно скажи об этом."
)

MAX_HISTORY_MESSAGES = 10  # сколько последних сообщений хранить в памяти на пользователя

# ===== INIT =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ai_client = OpenAI(
    api_key=YANDEX_API_KEY,
    base_url="https://llm.api.cloud.yandex.net/v1",
)

# Память диалогов: {user_id: [ {"role": "...", "content": "..."}, ... ]}
user_histories: dict[int, list[dict]] = {}


def get_history(user_id: int) -> list[dict]:
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]


def trim_history(history: list[dict]) -> None:
    # Оставляем только последние N сообщений, чтобы не разрастался запрос
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[: len(history) - MAX_HISTORY_MESSAGES]


async def ask_ai(user_id: int, user_text: str) -> str:
    history = get_history(user_id)
    history.append({"role": "user", "content": user_text})
    trim_history(history)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    try:
        response = ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI request error: {e}")
        return "Извините, сейчас не получилось получить ответ от AI. Попробуйте чуть позже."

    history.append({"role": "assistant", "content": answer})
    trim_history(history)
    return answer


# ===== HANDLERS =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_histories[message.from_user.id] = []  # чистый старт
    await message.answer(
        "👋 Привет! Я AI-ассистент на базе YandexGPT.\n\n"
        "Просто напишите вопрос — я отвечу.\n"
        "Команда /reset — очистить историю диалога."
    )


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_histories[message.from_user.id] = []
    await message.answer("🔄 История диалога очищена. Начнём заново!")


@dp.message(F.text)
async def handle_message(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    answer = await ask_ai(message.from_user.id, message.text)
    await message.answer(answer)


# ===== MAIN =====
async def main():
    logger.info("AI bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
