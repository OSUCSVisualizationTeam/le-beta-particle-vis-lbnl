from PySide6.QtCore import QObject
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl


class MainViewModel(QObject):
    def __init__(self):
        super().__init__()
        # Central source of truth for configuration
        self.configService = YAMLBackedConfigurationService()
        self.physicsManager = PhysicsConversionManagerImpl(self.configService)

        # Placeholder for application state
        self.isLiveMode = False
