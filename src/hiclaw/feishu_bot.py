from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    GetMessageResourceRequest,
    P2ImMessageReceiveV1,
)

from hiclaw.agent_client import AgentServiceError, run_agent
from hiclaw.agent_response import AgentReply
from hiclaw.config import (
    FEISHU_ALLOWED_CHAT_IDS,
    FEISHU_ALLOWED_OPEN_IDS,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_REPLY_PROCESSING_MESSAGE,
    FEISHU_SESSION_SCOPE_PREFIX,
)
from hiclaw.media_store import PhotoPayload

logger = logging.getLogger(__name__)


def parse_csv_set(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


ALLOWED_OPEN_IDS = parse_csv_set(FEISHU_ALLOWED_OPEN_IDS)
ALLOWED_CHAT_IDS = parse_csv_set(FEISHU_ALLOWED_CHAT_IDS)
SEEN_MESSAGE_IDS: set[str] = set()

# 飞书交互式卡片消息使用 lark_md 标签，原生支持 Markdown 渲染。


@dataclass(slots=True)
class FeishuIncomingMessage:
    message_id: str
    chat_id: str
    sender_open_id: str
    chat_type: str
    text: str = ""
    image_key: str | None = None


@dataclass(slots=True)
class FeishuBotAdapter:
    client: lark.Client

    async def send_message(self, chat_id: str, text: str) -> None:
        await send_text_message(self.client, chat_id, text)


def ensure_feishu_config() -> None:
    if not FEISHU_APP_ID:
        raise RuntimeError("FEISHU_APP_ID is required when starting the Feishu bot.")
    if not FEISHU_APP_SECRET:
        raise RuntimeError("FEISHU_APP_SECRET is required when starting the Feishu bot.")


def build_feishu_client() -> lark.Client:
    ensure_feishu_config()
    return lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()


def build_session_scope(message: FeishuIncomingMessage) -> str:
    if message.chat_type == "p2p":
        return f"{FEISHU_SESSION_SCOPE_PREFIX}:p2p:{message.sender_open_id}"
    return f"{FEISHU_SESSION_SCOPE_PREFIX}:chat:{message.chat_id}"


def is_allowed_message(message: FeishuIncomingMessage) -> bool:
    if not ALLOWED_OPEN_IDS and not ALLOWED_CHAT_IDS:
        return True
    return message.sender_open_id in ALLOWED_OPEN_IDS or message.chat_id in ALLOWED_CHAT_IDS


def is_duplicate(message_id: str) -> bool:
    if not message_id:
        return False
    if message_id in SEEN_MESSAGE_IDS:
        return True
    SEEN_MESSAGE_IDS.add(message_id)
    if len(SEEN_MESSAGE_IDS) > 1000:
        SEEN_MESSAGE_IDS.clear()
    return False


def extract_text_content(raw_content: str) -> str:
    try:
        content = json.loads(raw_content or "{}")
    except json.JSONDecodeError:
        return raw_content.strip()

    text = content.get("text")
    return text.strip() if isinstance(text, str) else ""


def get_nested_attr(obj: Any, path: str, default: Any = "") -> Any:
    current = obj
    for name in path.split("."):
        current = getattr(current, name, None)
        if current is None:
            return default
    return current


def parse_incoming_message(data: P2ImMessageReceiveV1) -> FeishuIncomingMessage | None:
    event = getattr(data, "event", None)
    message = getattr(event, "message", None)
    if message is None:
        return None

    message_type = getattr(message, "message_type", "")
    if message_type not in {"text", "image"}:
        return None

    if message_type == "image":
        content = json.loads(getattr(message, "content", "{}") or "{}")
        image_key = content.get("image_key", "")
        if not image_key:
            return None
        return FeishuIncomingMessage(
            message_id=getattr(message, "message_id", ""),
            chat_id=getattr(message, "chat_id", ""),
            sender_open_id=get_nested_attr(event, "sender.sender_id.open_id"),
            chat_type=getattr(message, "chat_type", ""),
            image_key=image_key,
        )

    return FeishuIncomingMessage(
        message_id=getattr(message, "message_id", ""),
        chat_id=getattr(message, "chat_id", ""),
        sender_open_id=get_nested_attr(event, "sender.sender_id.open_id"),
        chat_type=getattr(message, "chat_type", ""),
        text=extract_text_content(getattr(message, "content", "")),
    )


async def download_image(client: lark.Client, message_id: str, file_key: str) -> bytes:
    """把飞书图片下载到内存。"""

    request = (
        GetMessageResourceRequest.builder()
        .message_id(message_id)
        .file_key(file_key)
        .type("image")
        .build()
    )
    response = await client.im.v1.message_resource.aget(request)
    if response.file is not None:
        return response.file.read()
    raw = getattr(response, "raw", None)
    raw_content = getattr(raw, "content", b"") if raw else b""
    detail = raw_content.decode("utf-8", errors="replace") if raw_content else ""
    raise RuntimeError(f"Feishu image download failed: code={response.code}, msg={response.msg}, detail={detail}")


async def send_text_message(client: lark.Client, chat_id: str, text: str) -> None:
    """发送交互式富文本卡片消息，lark_md 原生支持 Markdown 渲染。"""

    if not text.strip():
        return

    card = {
        "config": {"wide_screen_mode": True},
        "elements": [
            {
                "tag": "div",
                "text": {"content": text, "tag": "lark_md"},
            },
        ],
    }

    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("interactive")
            .content(json.dumps(card, ensure_ascii=False))
            .build()
        )
        .build()
    )

    response = await client.im.v1.message.acreate(request)
    if not response.success():
        raise RuntimeError(f"Feishu send message failed: code={response.code}, msg={response.msg}")


async def reply_agent_result(client: lark.Client, chat_id: str, reply: AgentReply) -> None:
    if reply.text.strip():
        await send_text_message(client, chat_id, reply.text)

    if reply.images:
        await send_text_message(client, chat_id, "当前飞书第一版通道暂不支持发送图片结果，请先在 Telegram 或 TUI 通道查看图片。")


async def handle_message(client: lark.Client, incoming: FeishuIncomingMessage) -> None:
    if is_duplicate(incoming.message_id):
        logger.info("Skip duplicate Feishu message: %s", incoming.message_id)
        return

    if not incoming.text and not incoming.image_key:
        return

    if not is_allowed_message(incoming):
        logger.info("Skip unauthorized Feishu message: sender=%s chat=%s", incoming.sender_open_id, incoming.chat_id)
        return

    if FEISHU_REPLY_PROCESSING_MESSAGE:
        await send_text_message(client, incoming.chat_id, "收到，正在处理...")

    bot = FeishuBotAdapter(client)
    try:
        if incoming.image_key:
            image_data = await download_image(client, incoming.message_id, incoming.image_key)
            photo_payload = PhotoPayload(data=image_data, mime_type="image/jpeg")
            caption = incoming.text or "无"
            prompt = (
                "用户上传了一张图片。\n"
                f"用户附带说明：{caption}\n\n"
                "请先调用 get_uploaded_image 工具获取本轮图片内容，"
                "再结合图片和用户说明进行分析，并直接给出有帮助的中文回答。"
            )
            record_text = f"[Feishu] 用户上传了一张图片。说明：{caption}"
        else:
            prompt = incoming.text
            record_text = f"[Feishu] {incoming.text}"
            photo_payload = None

        reply = await run_agent(
            prompt=prompt,
            bot=bot,
            chat_id=incoming.chat_id,
            continue_session=True,
            record_text=record_text,
            uploaded_image=photo_payload,
            session_scope=build_session_scope(incoming),
        )
        await reply_agent_result(client, incoming.chat_id, reply)
    except AgentServiceError as exc:
        await send_text_message(client, incoming.chat_id, f"抱歉，这次调用模型服务失败了：{exc}")
    except Exception as exc:
        logger.exception("Feishu message handling failed")
        await send_text_message(client, incoming.chat_id, f"抱歉，飞书通道处理失败了：{exc}")


def build_event_handler(client: lark.Client):
    def on_message(data: P2ImMessageReceiveV1) -> None:
        incoming = parse_incoming_message(data)
        if incoming is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(handle_message(client, incoming))
        else:
            loop.create_task(handle_message(client, incoming))

    return lark.EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message).build()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = build_feishu_client()
    event_handler = build_event_handler(client)
    ws_client = lark.ws.Client(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )
    print("Feishu bot is running with WebSocket long connection...")
    ws_client.start()


if __name__ == "__main__":
    main()
