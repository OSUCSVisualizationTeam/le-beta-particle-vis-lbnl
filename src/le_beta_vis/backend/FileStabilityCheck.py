import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


def wait_for_file_stable(
    path: str,
    poll_interval_ms: int,
    max_wait_ms: int,
    stop_event: threading.Event | None = None,
) -> bool:
    """Block until *path*'s size stops changing across two consecutive polls.

    Returns True once the file is stable, or False if it never stabilizes
    within max_wait_ms, is deleted while being polled, or stop_event is set.
    """
    try:
        previous_size = os.stat(path).st_size
    except OSError:
        logger.warning(f"Cannot stat {path}: file missing or inaccessible.")
        return False

    poll_interval_s = poll_interval_ms / 1000
    deadline = time.monotonic() + (max_wait_ms / 1000)

    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            logger.debug(f"Stability wait for {path} aborted: stop_event set.")
            return False

        time.sleep(poll_interval_s)

        try:
            current_size = os.stat(path).st_size
        except OSError:
            logger.warning(f"{path} disappeared while waiting for it to stabilize.")
            return False

        if current_size == previous_size:
            return True
        previous_size = current_size

    logger.warning(f"{path} did not stabilize within {max_wait_ms}ms.")
    return False
