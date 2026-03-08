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
            EPS = EventPersistence()
            polling = PollingThread()
            self.EPS.start(EPS)
            self.Polling.start(polling)
        except Exception as e:
            logger.error(f"There was an issue starting the EPS and file ingest. {e}")

    def stop_all(self):
        """Stop EPS and Polling threads from service manager."""
        self.EPS.stop()
        self.Polling.stop()