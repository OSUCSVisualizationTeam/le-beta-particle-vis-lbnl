from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


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

    @abstractmethod
    def get_description(self, key: str) -> Optional[str]:
        """Return the human-readable description for *key*, or None."""
        raise NotImplementedError

    @abstractmethod
    def reset_to_defaults(self) -> None:
        """Reset all keys to their bundled default values."""
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Return structured metadata for all configuration keys."""
        raise NotImplementedError

    # --- Typed getters (concrete — inherited by all subclasses) ---

    def get_int(self, key: str, default: int, *,
                minimum: Optional[int] = None,
                maximum: Optional[int] = None) -> int:
        """Return *key* as ``int``, clamped to [minimum, maximum]."""
        value = int(self.get(key, default))
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def get_float(self, key: str, default: float, *,
                  minimum: Optional[float] = None,
                  maximum: Optional[float] = None) -> float:
        """Return *key* as ``float``, clamped to [minimum, maximum]."""
        value = float(self.get(key, default))
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def get_bool(self, key: str, default: bool) -> bool:
        """Return *key* as ``bool``."""
        return bool(self.get(key, default))
