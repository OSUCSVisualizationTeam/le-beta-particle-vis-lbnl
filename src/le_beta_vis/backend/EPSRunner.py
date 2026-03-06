import threading
import logging
from typing import Optional
from .EventPersistenceService import EventPersistence
from .InitializePolling import PollingThread
import zmq

logger = logging.getLogger(__name__)

class EPSRunner:
    """Initializes the EventPersistenceService and maintains thread execution."""
    def __init__(self):
        self.thread = Optional[threading.Thread] = None
        self.running = False

    def start(self, EPS: EventPersistence):
        """Starts the EPS in a daemon thread, checks if already running and calls run on EPS."""
        if self.running:
            logger.warning("EPS is already running.")
            return
        self.running = True
        self.thread = threading.Thread(
            target=self.run,
            args=(EPS,),
            daemon=True
        )
        self.thread.start()
        logger.info("EPS has started.")

    def run(self, EPS: EventPersistence):
        """Initializes EPS and catches exceptions."""
        try:
            EPS()
        except Exception as e:
            logger.error(f"Issue with EPS: {e}")
            self.running = False

    def stop(self):
        """Kills EPS by sending Kill to EPS command endpoint."""
        try:
            context = zmq.Context()
            command_socket = context.socket(zmq.REQ)
            command_socket.connect("ipc:///tmp/EPCCommand.ipc")
            command_socket.send_json({"Command": "Kill"})
            command_socket.recv_json()
            command_socket.close()
            context.term()
            logger.info("EPS sent kill command.")
        except Exception as e:
            logger.error(f"Failed to Kill EPS: {e}")

    def is_running(self):
        """Checks if EPS service is running."""
        # If running and thread is alive, it counts as the EPS running. 
        return self.running and self.thread.is_alive()
