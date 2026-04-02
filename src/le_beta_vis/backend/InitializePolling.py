from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import os
import time
import sys
import queue
from pathlib import Path
import threading
import logging

# Needed for local imports, can be removed later when called by main program
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from le_beta_vis.common.YAMLBackedConfigurationService import YAMLBackedConfigurationService
from le_beta_vis.backend.FileProcessing import process_file

logger = logging.getLogger(__name__)

class PollingThread():
    """
    Polling thread class for input database, location determined from configuration service.
    Manages starting polls and processing.
    """
    def __init__(self, config_service=None):

        # Temporary polling location, will be taken from config_service.get("pipeline:ingress:polling_location")
        # Modify this path for testing
        self.config_service = config_service or YAMLBackedConfigurationService()
        self.polling_location = os.path.normpath(self.config_service.get("pipeline:ingress:polling_location"))

        # Early exit in polling operations if the path doesn't exist, can add logging here later
        if not os.path.exists(self.polling_location):
            logger.error("Configured File Ingest path does not exist. Change in configuration and restart.")
        #Ensure temp and processed dirs are created and set
        # os.makedirs(os.path.join(self.polling_location, "/_temp"), exist_ok=True)
        # os.makedirs(os.path.join(self.polling_location, "/Processed"), exist_ok=True)
        # self.temp_processing = os.path.join(self.polling_location, "/_temp")
        # self.completed = os.path.join(self.polling_location, "/Processed")

        self.file_queue = queue.Queue()
        self.handler = EventHandler(self.file_queue)
        self.stop_event = threading.Event()
        # Do not call begin here, let PollingRunner manage

    def __call__(self):
        """Makes PollingThread callable for PollingRunner."""
        self.begin()

    def begin(self):
        """
        Begins polling the configured location with an observer
        """
        self.observer = FileWatcher(self.handler, self.polling_location)
        time.sleep(1)
        self.ingest_thread = threading.Thread(target=self.file_uploaded, args=(self.file_queue, self.config_service, self.stop_event))
        self.ingest_thread.start()

    def end(self):
        """Kills outstanding worker threads when polling stops."""
        self.stop_event.set()
        self.observer.stop()
        self.ingest_thread.join()

    def file_uploaded(self, queue: queue.Queue, config: YAMLBackedConfigurationService, stop_event: threading.Event):
        while not stop_event.is_set():
            try:
                path = queue.get(timeout=1)  # Wait for 1 second
                file_type = os.path.splitext(path)[1] # return extension of file in queue
                if file_type.lower() != '.fits':
                    continue
                process_file(config_service=config, file=path)
            except:
                continue

class EventHandler(FileSystemEventHandler):
    """
    Sub-class of Watchdog's FileSystemEventHandler, adds to queue when new files are created in polling directory.
    """
    def __init__(self, queue):
        self.event_queue = queue

    def on_created(self, event):
        """Handles events when files are created in watched directory, does not update for created directories."""
        super().on_created(event)
        if not event.is_directory:
            logger.info("New file creation polled.")
            self.event_queue.put(event.src_path)

    def on_moved(self, event):
        """Handles file move events and queues destination path for moved files."""
        super().on_moved(event)
        if not event.is_directory:
            moved_path = getattr(event, "dest_path", None)
            if moved_path:
                logger.info("New file moved in polling")
                self.event_queue.put(moved_path)

class FileWatcher():
    """
    FileWatcher class that instantiates an observer object to watch for changes in the directory
    """
    def __init__(self, handler: EventHandler, path: str):
        self.handler = handler
        self.path = path
        self.observer = Observer()
        self.observe()

    def observe(self):
        """Schedules observer and starts activity."""
        self.observer.schedule(self.handler, self.path, recursive=False)
        self.observer.start()

    def stop(self):
        self.observer.stop()
