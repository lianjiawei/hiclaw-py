import asyncio
import logging
import time

from hiclaw.channel_registry import get_registered_channels, start_background_channel
from hiclaw.delivery import DeliveryRouter
from hiclaw.scheduler_runtime import start_background_scheduler, stop_background_scheduler
from hiclaw.scheduler_store import init_task_db
from hiclaw.session_store import init_session_db

logger = logging.getLogger(__name__)


def _bootstrap_runtime_state() -> None:
    asyncio.run(init_task_db())
    asyncio.run(init_session_db())


def main() -> None:
    """统一入口：检测配置后启动所有已配置的通道。"""

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.CRITICAL)
    logging.getLogger("telegram.ext._utils.networkloop").setLevel(logging.CRITICAL)
    logging.getLogger("telegram.ext._updater").setLevel(logging.CRITICAL)

    available_channels = [channel for channel in get_registered_channels() if channel.enabled()]
    if not available_channels:
        raise RuntimeError(
            "Neither TELEGRAM_BOT_TOKEN nor FEISHU_APP_ID/FEISHU_APP_SECRET is configured. "
            "If you only want a local console, run `hiclaw-tui`."
        )

    print(f"Starting channels: {', '.join(channel.name for channel in available_channels)}")

    _bootstrap_runtime_state()
    router = DeliveryRouter()
    for channel in available_channels:
        channel.register_sender(router)

    scheduler_runtime = start_background_scheduler(router)

    background_threads = []
    foreground_runner = None
    for channel in available_channels:
        starter = channel.start()
        if starter is not None:
            if channel.run_in_background:
                background_threads.append(start_background_channel(channel.name, starter))
            elif foreground_runner is None:
                foreground_runner = starter
            else:
                background_threads.append(start_background_channel(channel.name, starter))

    if background_threads:
        time.sleep(2)

    try:
        if foreground_runner is not None:
            foreground_runner.start()
        elif background_threads:
            print("No foreground channel configured. Waiting for background channels...")
            try:
                while any(thread.is_alive() for thread in background_threads):
                    for thread in background_threads:
                        thread.join(timeout=0.5)
            except KeyboardInterrupt:
                print("Bot stopped.")
    finally:
        stop_background_scheduler(scheduler_runtime)


if __name__ == "__main__":
    main()
