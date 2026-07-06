"""
Telegram-бот для общения с кандидатами (при handoff и не только).
"""

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from src.core.audit_logger import audit_log
from src.core.config import get_settings
from src.services.audio_converter import convert_to_pcm
from src.services.handoff_service import HandoffService
from src.voice.pipeline import VoicePipeline

_settings = get_settings()
_logger = audit_log()
_handoff = HandoffService()
_voice_pipeline = VoicePipeline()

bot = Bot(token=_settings.telegram_bot_token)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = str(message.from_user.id)
    _logger.info("telegram_start", user_id=user_id)
    await message.answer(
        "Здравствуйте! Вы обратились в MassRecruitHub. "
        "Если у вас есть активный диалог с нашим рекрутером, он продолжится здесь. "
        "Для начала нового диалога, пожалуйста, укажите ваш номер телефона."
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start – начать диалог\n"
        "/help – эта справка\n"
        "/cancel – отменить текущий диалог\n"
        "Просто напишите сообщение, и мы ответим."
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message):
    user_id = str(message.from_user.id)
    await _handoff.delete_state(user_id)
    await message.answer("Диалог отменён. Если передумаете, напишите снова.")


@dp.message(lambda message: message.voice is not None)
async def handle_voice(message: Message):
    """Обработка голосовых сообщений в Telegram."""
    user_id = str(message.from_user.id)
    _logger.info("telegram_voice_received", user_id=user_id)

    file = await bot.get_file(message.voice.file_id)
    file_bytes = await bot.download_file(file.file_path)

    pcm_bytes = await convert_to_pcm(file_bytes, input_format="ogg")
    if not pcm_bytes:
        await message.reply(
            "Не удалось обработать голосовое сообщение. Попробуйте отправить текст."
        )
        return

    text = await _voice_pipeline.transcribe_bytes(pcm_bytes)
    if not text:
        await message.reply("Не удалось распознать голос. Пожалуйста, повторите чётче.")
        return

    state = await _handoff.load_state(user_id)
    if state:
        response = f"Вы сказали: {text}. Скоро с вами свяжутся."
        await message.answer(response)
    else:
        await message.answer(
            "У вас нет активного диалога. Пожалуйста, используйте /start, чтобы начать, "
            "или свяжитесь с нами по телефону."
        )


@dp.message()
async def handle_text(message: Message):
    user_id = str(message.from_user.id)
    text = message.text
    _logger.info("telegram_message", user_id=user_id, text_preview=text[:50])

    state = await _handoff.load_state(user_id)
    if state:
        response = f"Продолжаем разговор. Вы написали: {text}. Скоро с вами свяжутся."
        await message.answer(response)
    else:
        await message.answer(
            "У вас нет активного диалога. Пожалуйста, используйте /start, чтобы начать, "
            "или свяжитесь с нами по телефону."
        )


async def set_webhook() -> None:
    webhook_url = _settings.telegram_webhook_url
    if webhook_url:
        await bot.set_webhook(webhook_url)
        _logger.info("telegram_webhook_set", url=webhook_url)
    else:
        _logger.warning("telegram_webhook_url not set, using polling")


async def on_startup():
    await set_webhook()


async def on_shutdown():
    await bot.session.close()


def get_dispatcher() -> Dispatcher:
    return dp
