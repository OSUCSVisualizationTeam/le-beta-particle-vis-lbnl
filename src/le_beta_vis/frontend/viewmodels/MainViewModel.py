from PySide6.QtCore import QObject
from le_beta_vis.common.ConfigurationService import (
    ConfigurationService,
    MockConfigurationService,
)


class MainViewModel(QObject):
    def __init__(self):
        super().__init__()
        # Central source of truth for configuration
        self.configService = MockConfigurationService()

        # Placeholder for application state
        self.isLiveMode = False
