from PySide6.QtCore import QObject
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository
from le_beta_vis.common.PrefetchingThumbnailLoaderService import (
    PrefetchingThumbnailLoaderService,
)
from le_beta_vis.frontend.fitsconverters.interface import Colormap


class MainViewModel(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.configService = YAMLBackedConfigurationService()
        self.physicsManager = PhysicsConversionManagerImpl(self.configService)
        self.isLiveMode = False
        self.eventRepository: EventRepository = self._createEventRepository()
        self.thumbnailService: ThumbnailLoaderService = self._createThumbnailService()

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
