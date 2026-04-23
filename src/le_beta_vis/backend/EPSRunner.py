import threading
import logging
from typing import Optional
from .EventPersistenceService import EventPersistence
from .InitializePolling import PollingThread
from le_beta_vis.common.YAMLBackedConfigurationService import YAMLBackedConfigurationService
from le_beta_vis.common.ZMQEventHandlerClient import DEFAULT_EVENT_PUB_ENDPOINT
from le_beta_vis.common.ZMQEventLoggingHandler import attach_to_root_logger
import zmq

logger = logging.getLogger(__name__)


class EPSRunner:
    """Initializes the EventPersistenceService and maintains thread execution."""

    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.config = YAMLBackedConfigurationService()
        self._log_handler = attach_to_root_logger(
            endpoint=self.config.get("event_handler:zmq_pub_endpoint")
            or DEFAULT_EVENT_PUB_ENDPOINT,
            source="eps",
        )

    def start(self):
        """Starts the EPS in a daemon thread, checks if already running and calls run on EPS."""
        if self.running:
            logger.warning("EPS is already running.")
            return
        self.running = True
        self.thread = threading.Thread(
            target=self.run,
            daemon=True
        )
        self.thread.start()
        logger.info("EPS has started.")

    def run(self):
        """Initializes EPS and catches exceptions."""
        try:
            EventPersistence()
        except Exception as e:
            logger.error(f"Issue with EPS: {e}")
            self.running = False

    def stop(self):
        """Kills EPS by sending Kill to EPS command endpoint."""
        logging.root.removeHandler(self._log_handler)
        try:
            context = zmq.Context()
            command_socket = context.socket(zmq.REQ)
            command_socket.setsockopt(zmq.RCVTIMEO, 2000)
            command_socket.connect(self.config.get("eps:command_ipc"))
            command_socket.send_json({"Command": "Kill"})
            try:
                command_socket.recv_json()
            except BaseException:
                logger.warning("EPS did not respond to kill command.")
            command_socket.close()
            context.term()
            logger.info("EPS no longer running.")
        except Exception as e:
            logger.error(f"Failed to Kill EPS: {e}")
        finally:
            self.running = False

    def is_running(self):
        """Checks if EPS service is running."""
        # If running and thread is alive, it counts as the EPS running.
        return self.running and self.thread.is_alive()
