import os
from typing import Any, Dict, Optional

import redis
from dotenv import load_dotenv

from le_beta_vis.common.ConfigurationService import ConfigurationService


class RedisBackedConfigurationService(ConfigurationService):
    """
    Redis-backed implementation of the ConfigurationService interface.

    Provides low-latency key-value access to system configuration using Redis
    as the fast-path cache layer, as specified in Design Doc Section 6.

    Reads connection parameters from environment variables:
      REDIS_HOST     (default: 127.0.0.1)
      REDIS_PORT     (default: 6379)
      REDIS_PASSWORD (required)
    """

    _TYPE_REGISTRY: Dict[str, type] = {
        # Global / Infrastructure
        "global:db:connection_string": str,
        "global:db:username": str,
        "global:db:password": str,

        "global:redis:host": str,
        "global:redis:port": int,
        "global:redis:channel_events": str,

        "global:physics:kev_conversion": float,
        "global:physics:ped_width": int,

        # GUI - Raw Analysis
        "gui:raw_analysis:default_colormap": str,
        "gui:raw_analysis:vis_range_min": float,
        "gui:raw_analysis:vis_range_max": float,
        "gui:raw_analysis:filter_gaussian_sigma": float,
        "gui:raw_analysis:clustering_threshold": float,
        "gui:raw_analysis:cluster_extractor_method": str,
        "gui:raw_analysis:zoom_step_factor": float,
        "gui:raw_analysis:magnifier_display_size": int,
        "gui:raw_analysis:magnifier_default_factor": float,
        "gui:raw_analysis:magnifier_min_factor": float,
        "gui:raw_analysis:magnifier_max_factor": float,
        "gui:raw_analysis:magnifier_factor_step": float,
        "gui:raw_analysis:magnifier_move_step": int,
        "gui:raw_analysis:show_tool_hints": bool,
        "gui:raw_analysis:box_select_color": str,
        "gui:raw_analysis:box_select_border_width": int,

        # GUI - Window
        "gui:window:default_width": int,
        "gui:window:default_height": int,

        # GUI - Mosaic
        "gui:mosaic:height": int,
        "gui:mosaic:thumbnail_height": int,
        "gui:mosaic:scaling_function": str,

        # GUI - Historical
        "gui:historical:default_time_preset": str,
        "gui:historical:live_update_rate_ms": int,
        "gui:historical:mode": str,

        # GUI - Inspector
        "gui:inspector:histogram_bins": int,

        # GUI - Export
        "gui:export:default_path": str,
        "gui:export:image_format": str,
    }

    def __init__(self):
        raise NotImplementedError(
            "RedisBackedConfigurationService is deprecated. "
            "Use YAMLBackedConfigurationService instead."
        )
        load_dotenv()  # Explicit, controlled — runs only when the class is instantiated

        host = os.getenv("REDIS_HOST", "127.0.0.1")
        port = int(os.getenv("REDIS_PORT", "6379"))
        password = os.getenv("REDIS_PASSWORD")

        if not password:
            raise RuntimeError(
                "REDIS_PASSWORD is not set. Add it to your environment or .env file."
            )

        self._client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,
        )

    def ping(self) -> bool:
        return self._client.ping()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value by key, coercing it to the correct
        Python type based on the type registry. Returns `default` if the
        key does not exist in Redis.
        """
        raw = self._client.get(key)
        if raw is None:
            return default
        return self._coerce(key, raw)

    def set(self, key: str, value: Any) -> None:
        """
        Persist a configuration value. Booleans are stored as the strings
        'true'/'false'; all other types are stored via str().
        """
        self._client.set(key, self._serialize(value))

    def get_description(self, key: str) -> Optional[str]:
        """Return None — Redis backend has no description metadata."""
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _serialize(self, value: Any) -> str:
        """Convert a Python value to a Redis-safe string."""
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    def _coerce(self, key: str, raw: str) -> Any:
        """Cast a raw Redis string back to the expected Python type."""
        target_type = self._TYPE_REGISTRY.get(key)
        if target_type is int:
            return int(raw)
        if target_type is float:
            return float(raw)
        # Boolean convention: stored as 'true'/'false'
        if raw.lower() == "true":
            return True
        if raw.lower() == "false":
            return False
        return raw  # plain string
