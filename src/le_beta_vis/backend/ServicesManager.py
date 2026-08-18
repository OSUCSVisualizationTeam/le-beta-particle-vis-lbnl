import sys
import os
import logging

from .EPSRunner import EPSRunner
from .PollingRunner import PollingRunner
from .EventPersistenceService import EventPersistence
from .InitializePolling import PollingThread

logger = logging.getLogger(__name__)


class ServicesManager:
    """Intializes backend services, handles starting daemons."""

    def __init__(self):
        self.EPS = EPSRunner()
        self.Polling = PollingRunner()

    def start_all(self):
        """Start EPS and Polling with EPS and Polling threads."""
        try:
            polling = PollingThread()
            self.EPS.start()
            self.Polling.start(polling)
        except Exception as e:
            logger.error(f"There was an issue starting the EPS and file ingest. {e}")

    def stop_all(self):
        """Stop EPS and Polling threads from service manager.

        Polling must stop first: it drains in-flight ingestion work that
        talks to EPS over ZMQ, and that only returns promptly while EPS is
        still alive to reply. Stopping EPS first leaves those requests
        waiting on a server that's already gone.
        """
        self.Polling.stop()
        self.EPS.stop()

    def restart(self):
        """Restart EPS and Polling threads from service manager."""
        self.stop_all()
        self.EPS = EPSRunner()
        self.Polling = PollingRunner()
        self.start_all()
