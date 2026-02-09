from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
import os
import time
import sys
import queue
from pathlib import Path
import threading

# Needed for local imports, can be removed later when called by main program
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.backend.FileProcessing import ProcessFile

config = MockConfigurationService()

class PollingThread():
    """
    Polling thread class for input database, location determined from configuration service.
    Manages starting polls and processing.
    """
    def __init__(self, config_service: MockConfigurationService):

        # Temporary polling location, will be taken from config_service.get("pipeline:ingress:polling_location")
        # Modify this path for testing

        self.polling_location = config_service.get("pipeline:ingress:polling_location")

        #Ensure temp and processed dirs are created and set
        # os.makedirs(os.path.join(self.polling_location, "/_temp"), exist_ok=True)
        # os.makedirs(os.path.join(self.polling_location, "/Processed"), exist_ok=True)
        # self.temp_processing = os.path.join(self.polling_location, "/_temp")
        # self.completed = os.path.join(self.polling_location, "/Processed")

        self.file_queue = queue.Queue()
        self.handler = EventHandler(self.file_queue)

    def begin(self):
        """
        Begins polling the configured location with an observer
        """
        self.observer = FileWatcher(self.handler, self.polling_location)
        self.ingest = threading.Thread(target=file_uploaded, args=(self.file_queue, config), daemon=True)
        self.ingest.start()

    def end(self):
        """Kills outstanding worker threads when polling stops."""
        self.observer.stop()
        self.ingest.stop()

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
                self.event_queue.put(event.src_path)

class FileWatcher():
    """
    FileWatcher class that instantiates an observer object to watch for changes in the directory
    """
    def __init__(self, handler: EventHandler, path: Path):
        self.handler = handler
        self.path = path
        self.observer = Observer()
        self.observe()

    def observe(self):
        """Schedules observer and starts activity."""
        self.observer.schedule(self.handler, self.path, recursive=False)
        self.observer.start()

def file_uploaded(queue: queue.Queue, config: MockConfigurationService):
    while True:
        path = queue.get()
        file_type = os.path.splitext(path)[1] # return extension of file in queue
        if file_type.lower() != '.fits':
            continue
        ProcessFile(config_service=config, file=path)

if __name__ == "__main__":
    polling = PollingThread(config)
    polling.begin()