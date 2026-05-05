from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any

from hiclaw.core.delivery import DeliveryRouter
from hiclaw.tasks.scheduler import setup_scheduler

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BackgroundSchedulerRuntime:
    scheduler: Any
    loop: asyncio.AbstractEventLoop
    thread: threading.Thread


def start_background_scheduler(router: DeliveryRouter) -> BackgroundSchedulerRuntime:
    # App mode owns a dedicated scheduler loop thread so channel event loops stay independent.
    ready = threading.Event()
    state: dict[str, object] = {}
    startup_error: list[BaseException] = []

    def run_scheduler_loop() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            scheduler = setup_scheduler(router, event_loop=loop)
            scheduler.start()
        except BaseException as exc:
            startup_error.append(exc)
            logger.exception("Scheduler startup failed")
            ready.set()
            loop.close()
            return

        state["loop"] = loop
        state["scheduler"] = scheduler
        ready.set()
        logger.info("Scheduler loop started in background thread")
        loop.run_forever()
        logger.info("Scheduler loop stopping")
        loop.close()

    thread = threading.Thread(target=run_scheduler_loop, daemon=True, name="hiclaw-scheduler")
    thread.start()
    ready.wait()
    if startup_error:
        raise RuntimeError("Failed to start background scheduler.") from startup_error[0]
    logger.info("Scheduler runtime ready")
    return BackgroundSchedulerRuntime(
        scheduler=state["scheduler"],
        loop=state["loop"],
        thread=thread,
    )


def stop_background_scheduler(runtime: BackgroundSchedulerRuntime) -> None:
    def shutdown_scheduler() -> None:
        runtime.scheduler.shutdown(wait=False)
        runtime.loop.stop()

    if runtime.loop.is_running():
        runtime.loop.call_soon_threadsafe(shutdown_scheduler)
    runtime.thread.join(timeout=5)
    logger.info("Scheduler runtime stopped")
