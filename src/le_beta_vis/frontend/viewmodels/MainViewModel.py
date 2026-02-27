from PySide6.QtCore import QObject
from le_beta_vis.common.ConfigurationService import (
    MockConfigurationService,
)
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl


class MainViewModel(QObject):
    def __init__(self):
        super().__init__()
        # Central source of truth for configuration
        self.configService = MockConfigurationService()
        self.physicsManager = PhysicsConversionManagerImpl(self.configService)

        # Placeholder for application state
        self.isLiveMode = False
