import asyncio
import logging
import threading
import time

from telegram.error import NetworkError, TelegramError, TimedOut

from hiclaw.config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_RESTART_DELAY_SECONDS,
)
from hiclaw.telegram_bot import build_application, run_polling_options

logger = logging.getLogger(__name__)


def _start_feishu_in_thread() -> None:
    """在独立线程中启动飞书 WebSocket 长连接。"""

    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

    from hiclaw.config import FEISHU_APP_ID, FEISHU_APP_SECRET
    from hiclaw.feishu_bot import (
        build_event_handler,
        build_feishu_client,
        handle_message,
    )

    client = build_feishu_client()
    event_handler = build_event_handler(client)
    ws_client = lark.ws.Client(
        app_id=FEISHU_APP_ID,
        app_secret=FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )
    print("Feishu bot: WebSocket long connection started.")
    ws_client.start()


def _has_feishu_config() -> bool:
    return bool(FEISHU_APP_ID and FEISHU_APP_SECRET)


def _has_telegram_config() -> bool:
    return bool(TELEGRAM_BOT_TOKEN)


def main() -> None:
    """统一入口：检测配置后启动所有已配置的通道。"""

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext._utils.networkloop").setLevel(logging.CRITICAL)
    logging.getLogger("telegram.ext._updater").setLevel(logging.CRITICAL)

    if not _has_feishu_config() and not _has_telegram_config():
        raise RuntimeError("Neither TELEGRAM_BOT_TOKEN nor FEISHU_APP_ID/FEISHU_APP_SECRET is configured.")

    channels = []
    if _has_telegram_config():
        channels.append("Telegram")
    if _has_feishu_config():
        channels.append("Feishu")
    print(f"Starting channels: {', '.join(channels)}")

    # 如果同时配置了飞书，在独立线程中启动，不阻塞 Telegram 主循环。
    if _has_feishu_config():
        feishu_thread = threading.Thread(target=_start_feishu_in_thread, daemon=True, name="feishu-ws")
        feishu_thread.start()
        # 等飞书连接建立，确保线程启动成功。
        time.sleep(2)

    # Telegram 在主线程中运行（阻塞）。
    if _has_telegram_config():
        while True:
            try:
                app = build_application()
                app.run_polling(**run_polling_options())
            except KeyboardInterrupt:
                print("Bot stopped.")
                break
            except (TimedOut, NetworkError, TelegramError) as exc:
                logger.warning(
                    "Telegram polling failed: %s. Restarting in %s seconds...",
                    exc.__class__.__name__,
                    TELEGRAM_RESTART_DELAY_SECONDS,
                )
                time.sleep(TELEGRAM_RESTART_DELAY_SECONDS)
            except Exception:
                logger.exception(
                    "Bot crashed unexpectedly. Restarting in %s seconds...",
                    TELEGRAM_RESTART_DELAY_SECONDS,
                )
                time.sleep(TELEGRAM_RESTART_DELAY_SECONDS)
    else:
        # 只有飞书时，阻塞主线程防止退出。
        print("Telegram not configured. Waiting for Feishu...")
        try:
            feishu_thread.join()
        except KeyboardInterrupt:
            print("Bot stopped.")


if __name__ == "__main__":
    main()
