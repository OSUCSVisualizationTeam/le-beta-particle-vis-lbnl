import enum
import logging
import os
import platform
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from le_beta_vis.common.ConfigurationService import ConfigurationService

logger = logging.getLogger(__name__)

_BUNDLED_DEFAULTS_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"
)


class YAMLBackedConfigurationService(ConfigurationService):
    """YAML-file-backed implementation of ConfigurationService.

    Provides a human-editable configuration file at a well-known location.
    The in-memory store is loaded lazily on first access, and a type
    registry self-populates from ``get(key, default)`` calls so that
    hand-edited YAML strings can be coerced back to the expected type.
    """

    def __init__(self, yaml_path: Optional[Path] = None) -> None:
        self._yaml_path: Path = yaml_path or self._resolve_yaml_path()
        self._store: Optional[Dict[str, Any]] = None
        self._type_registry: Dict[str, str] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value by *key*.

        On a cache hit the raw value is coerced through the type registry
        and returned.  On a miss, *default* is stored, its type is
        registered, and the file is persisted so the key becomes visible
        to future edits.  If both the key is missing and *default* is
        ``None``, returns ``None`` without side-effects.
        """
        with self._lock:
            self._ensure_loaded()
            if key in self._store:
                return self._coerce(key, self._store[key])
            if default is not None:
                type_name = self._infer_type_name(default)
                self._type_registry[key] = type_name
                self._store[key] = self._normalize_value(default)
                self._persist()
                return self._normalize_value(default)
            return None

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key* and persist to disk."""
        with self._lock:
            self._ensure_loaded()
            if key not in self._type_registry:
                self._type_registry[key] = self._infer_type_name(value)
            self._store[key] = self._normalize_value(value)
            self._persist()

    def get_description(self, key: str) -> Optional[str]:
        """Return the human-readable description for *key*, or None."""
        metadata = self._load_bundled_defaults_metadata()
        entry = metadata.get(key)
        if entry is None:
            return None
        return entry.get("description")

    def get_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Return the full structured metadata from *defaults.yaml*.

        Each key maps to a dict with ``type``, ``default``, and
        ``description`` entries.  Intended for a future Configuration UI.
        """
        return self._load_bundled_defaults_metadata()

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_yaml_path() -> Path:
        """Return the first existing config path, or the first candidate."""
        candidates = YAMLBackedConfigurationService._config_candidates()
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @staticmethod
    def _config_candidates() -> list:
        """Build ordered list of candidate paths per platform."""
        candidates: list[Path] = []
        if platform.system() == "Windows":
            appdata = os.environ.get("APPDATA")
            if appdata:
                candidates.append(Path(appdata) / "mlccd_viz.yaml")
        else:
            home = Path.home()
            candidates.append(home / "mlccd_viz.yaml")
            xdg = os.environ.get(
                "XDG_CONFIG_HOME", str(home / ".config")
            )
            candidates.append(Path(xdg) / "mlccd_viz.yaml")
        candidates.append(Path.cwd() / "mlccd_viz.yaml")
        return candidates

    # ------------------------------------------------------------------
    # Lazy loading & persistence
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the YAML file on first access; bootstrap from defaults
        if the file does not exist yet."""
        if self._store is not None:
            return
        if self._yaml_path.exists():
            with open(self._yaml_path, "r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh)
            self._store = loaded if isinstance(loaded, dict) else {}
        else:
            self._store = self._load_bundled_defaults()
            self._persist()
            logger.info(
                "Created default configuration at %s", self._yaml_path
            )

    def _load_bundled_defaults(self) -> Dict[str, Any]:
        """Read structured *defaults.yaml* and return a flat dict."""
        metadata = self._load_bundled_defaults_metadata()
        return {key: entry["default"] for key, entry in metadata.items()}

    @staticmethod
    def _load_bundled_defaults_metadata() -> Dict[str, Dict[str, Any]]:
        """Read structured *defaults.yaml* and return full metadata."""
        if not _BUNDLED_DEFAULTS_PATH.exists():
            logger.warning(
                "Bundled defaults.yaml not found at %s",
                _BUNDLED_DEFAULTS_PATH,
            )
            return {}
        with open(_BUNDLED_DEFAULTS_PATH, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not isinstance(raw, dict):
            return {}
        return raw

    def _persist(self) -> None:
        """Write the current store to disk."""
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._yaml_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(
                self._store, fh,
                default_flow_style=False,
                sort_keys=True,
            )

    # ------------------------------------------------------------------
    # Type inference & coercion
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        """Convert non-YAML-safe types (e.g. Enum) to primitives."""
        if isinstance(value, enum.Enum):
            return value.value
        return value

    @staticmethod
    def _infer_type_name(value: Any) -> str:
        """Map a Python value to a registry type name string."""
        if isinstance(value, enum.Enum):
            value = value.value
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        return "str"

    def _coerce(self, key: str, raw: Any) -> Any:
        """Coerce *raw* to the registered type for *key*.

        If no type is registered, the value is returned as-is (YAML
        ``safe_load`` already returns native Python types).
        """
        type_name = self._type_registry.get(key)
        if type_name is None:
            return raw
        if type_name == "bool":
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                return raw.lower() in ("true", "1", "yes")
            return bool(raw)
        if type_name == "int":
            return int(raw)
        if type_name == "float":
            return float(raw)
        return str(raw)
