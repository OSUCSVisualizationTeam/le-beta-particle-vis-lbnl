import sys
import os

from .EPSRunner import EPSRunner
from .PollingRunner import PollingRunner
from .EventPersistenceService import EventPersistence
from .InitializePolling import PollingThread

class ServicesManager:
    """Intializes backend services, handles starting daemons."""
    def __init__(self):
        self.EPS = EPSRunner()
        self.Polling = PollingRunner()

    def start_all(self):
        """Start EPS and Polling with EPS and Polling threads."""
        EPS = EventPersistence()
        polling = PollingThread()
        self.EPS.start(EPS)
        self.Polling.start(polling)

    def stop_all(self):
        """Stop EPS and Polling threads from service manager."""
        self.EPS.stop()
        self.Polling.stop()