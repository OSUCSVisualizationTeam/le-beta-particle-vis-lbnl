import logging

from PySide6.QtCore import QObject

from le_beta_vis.common.EventHandler import EventHandler
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl
from le_beta_vis.common.PrefetchingThumbnailLoaderService import (
    PrefetchingThumbnailLoaderService,
)
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository
from le_beta_vis.common.ZMQEventHandlerSource import ZMQEventHandlerSource
from le_beta_vis.frontend.fitsconverters.interface import Colormap


logger = logging.getLogger(__name__)


_DEFAULT_EVENT_PUB_ENDPOINT = "ipc:///tmp/EPCEvents.ipc"


class MainViewModel(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.configService = YAMLBackedConfigurationService()
        self.physicsManager = PhysicsConversionManagerImpl(self.configService)
        self.isLiveMode = False
        self.eventRepository: EventRepository = self._createEventRepository()
        self.thumbnailService: ThumbnailLoaderService = self._createThumbnailService()
        self.eventHandler: EventHandlerInterface = EventHandler(self.configService)
        self.eventSource: ZMQEventHandlerSource = self._createEventSource()
        self.eventSource.start()

    def _createEventRepository(self) -> EventRepository:
        """Build the ZMQ-backed event repository from configuration."""
        return ZMQBasedEventRepository(self.configService)

    def _createThumbnailService(self) -> ThumbnailLoaderService:
        """Build the prefetching thumbnail loader from configuration."""
        cfg = self.configService
        colormap_str = str(cfg.get("gui:historical:thumbnail_colormap", "viridis"))
        max_workers = cfg.get_int(
            "gui:historical:thumbnail_max_workers", 2, minimum=2,
        )
        idle_seconds = cfg.get_int(
            "gui:historical:fits_cache_idle_seconds", 60, minimum=60,
        )
        return PrefetchingThumbnailLoaderService(
            max_workers=max_workers,
            colormap=Colormap(colormap_str),
            fits_cache_idle_seconds=idle_seconds,
        )

    def _createEventSource(self) -> ZMQEventHandlerSource:
        """Build the ZMQ SUB reader that feeds the EventHandler."""
        endpoint = str(
            self.configService.get(
                "event_handler:zmq_pub_endpoint",
                _DEFAULT_EVENT_PUB_ENDPOINT,
            )
        )
        return ZMQEventHandlerSource(
            endpoint=endpoint,
            event_handler=self.eventHandler,
            config=self.configService,
        )

    def shutdown(self) -> None:
        """Stops the event source and handler workers on app exit."""
        try:
            self.eventSource.shutdown()
        except Exception:
            logger.exception("Error shutting down ZMQEventHandlerSource")
        try:
            timeout_ms = self.configService.get_int(
                "event_handler:worker_join_timeout_ms", 2000, minimum=0,
            )
            self.eventHandler.shutdown(timeout_ms=timeout_ms)
        except Exception:
            logger.exception("Error shutting down EventHandler")
