from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from telegram import Message

from garveyclaw.config import UPLOAD_IMAGES_DIR, UPLOAD_VOICES_DIR


def _build_upload_name(prefix: str, suffix: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}_{uuid4().hex[:8]}{suffix}"


async def save_photo_message(message: Message) -> Path:
    """保存 Telegram 图片消息中尺寸最大的一张图片。"""

    if not message.photo:
        raise ValueError("Message does not contain a photo.")

    photo = message.photo[-1]
    telegram_file = await photo.get_file()
    file_path = UPLOAD_IMAGES_DIR / _build_upload_name("photo", ".jpg")
    await telegram_file.download_to_drive(custom_path=str(file_path))
    return file_path


async def save_voice_message(message: Message) -> Path:
    """保存 Telegram 语音消息，默认格式通常是 ogg/opus。"""

    if not message.voice:
        raise ValueError("Message does not contain a voice.")

    telegram_file = await message.voice.get_file()
    file_path = UPLOAD_VOICES_DIR / _build_upload_name("voice", ".ogg")
    await telegram_file.download_to_drive(custom_path=str(file_path))
    return file_path
