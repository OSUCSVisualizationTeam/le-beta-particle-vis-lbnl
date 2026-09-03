import threading
import logging
from typing import Optional
import time
from .InitializePolling import PollingThread

logger = logging.getLogger(__name__)


class PollingRunner:
    """Initializes the File Ingest Service and maintains thread execution."""

    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        # Save poller to clean up observer as well when killing file ingest
        self.poller: Optional[PollingThread] = None
        self.running = False

    def start(self, poller: PollingThread):
        """Starts the File Ingest in a daemon thread, checks if already running and calls run on PollingThread."""
        if self.running:
            logger.warning("File Ingest is already running.")
            return

        self.running = True
        self.poller = poller
        self.thread = threading.Thread(
            target=self.run,
            args=(poller,),
            daemon=True
        )
        self.thread.start()
        logger.info("File Ingest has started.")

    def run(self, poller: PollingThread):
        """Initializes File Ingest and catches exceptions."""
        try:
            poller()
            while self.running:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Issue with File Ingest: {e}")
            self.running = False

    def is_running(self) -> bool:
        """Checks if File Ingest is running."""
        # If running and thread is alive, it counts as the EPS running.
        return self.running and self.thread.is_alive()

    def stop(self):
        """Kills the File Ingest daemon and observer with PollingThread.end()"""
        if self.poller:
            self.poller.end()
        self.running = False
        logger.info("File Ingest stopped.")
