from abc import ABC, abstractmethod
from typing import Any, Dict


class ConfigurationService(ABC):
    """
    Abstract interface for the Configuration Management Service.
    Provides access to system-wide settings.
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value by key."""
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        raise NotImplementedError


class MockConfigurationService(ConfigurationService):
    """
    Temporary mock implementation of the Configuration Service.
    Returns hardcoded values derived STRICTLY from the design document's
    Configuration Management table and Q&A section.
    """

    def __init__(self):
        self._store: Dict[str, Any] = {
            # Global / Infrastructure
            "global:db:connection_string": "mysql://localhost/mlccd_viz",
            "global:redis:host": "localhost",
            "global:redis:port": 6379,
            "global:redis:channel_events": "events/new_class",
            # Physics (From Design Q&A section)
            "global:physics:kev_conversion": 1.02857e-5,
            "global:physics:ped_width": 1400,
            # Interactive Raw Data Analysis (GUI)
            "gui:raw_analysis:default_colormap": "viridis",
            "gui:raw_analysis:vis_range_min": 0.0,
            "gui:raw_analysis:vis_range_max": 20.0,
            "gui:raw_analysis:filter_gaussian_sigma": 1.5,
            "gui:raw_analysis:clustering_threshold": 4.0,
            "gui:raw_analysis:zoom_step_factor": 1.2,
            # Magnifier Tool
            "gui:raw_analysis:magnifier_display_size": 127,
            "gui:raw_analysis:magnifier_default_factor": 3.0,
            "gui:raw_analysis:magnifier_min_factor": 1.0,
            "gui:raw_analysis:magnifier_max_factor": 100.0,
            "gui:raw_analysis:magnifier_factor_step": 0.5,
            "gui:raw_analysis:magnifier_move_step": 1,
            "gui:raw_analysis:show_tool_hints": True,
            # Window Geometry
            "gui:window:default_width": 1024,
            "gui:window:default_height": 700,
            # Mosaic View
            "gui:mosaic:height": 130,
            "gui:mosaic:thumbnail_height": 100,
            "gui:mosaic:scaling_function": "log",
            # Historical Event Analysis (GUI)
            "gui:historical:default_query_hours": 24,
            "gui:historical:live_update_rate_ms": 1000,
            "gui:historical:mode": "historical",
            "gui:inspector:histogram_bins": 50,
            # Export & Reporting (GUI)
            "gui:export:default_path": "~/Data",
            "gui:export:image_format": "png",
            # Pipeline and Ingress
            "pipeline:ingress:polling_location": "~/Google\ Drive\/My\ Drive/FITS",
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
