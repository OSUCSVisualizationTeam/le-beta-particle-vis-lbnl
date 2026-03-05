"""Pure-Python ViewModel for the Settings dialog.

Tracks pending changes separately from live configuration values,
supports grouping by key namespace, and provides text filtering.
No Qt dependencies — testable in headless CI.
"""

from typing import (
    Any, Callable, Dict, List, Tuple,
)

from le_beta_vis.common.ConfigurationService import ConfigurationService

# (key, display_label, type_str, current_value, default_value, description, choices)
SettingEntry = Tuple[str, str, str, Any, Any, str, List[Any]]

# {group: {subgroup: [entries]}}
GroupedSettings = Dict[str, Dict[str, List[SettingEntry]]]

_ACRONYM_OVERRIDES: Dict[str, str] = {
    "gui": "GUI",
    "eps": "EPS",
    "db": "Database",
    "ipc": "IPC",
}


def _humanize(token: str) -> str:
    """Convert a snake_case token to Title Case with acronym overrides."""
    lower = token.lower()
    if lower in _ACRONYM_OVERRIDES:
        return _ACRONYM_OVERRIDES[lower]
    return token.replace("_", " ").title()


def _parse_key(key: str) -> Tuple[str, str, str]:
    """Split a colon-delimited key into (group, subgroup, leaf).

    Examples
    --------
    >>> _parse_key("gui:raw_analysis:clustering_threshold")
    ('GUI', 'Raw Analysis', 'Clustering Threshold')
    >>> _parse_key("eps:timeout_ms")
    ('EPS', 'General', 'Timeout Ms')
    """
    parts = key.split(":")
    if len(parts) >= 3:
        group = _humanize(parts[0])
        subgroup = _humanize(":".join(parts[1:-1]))
        leaf = _humanize(parts[-1])
    elif len(parts) == 2:
        group = _humanize(parts[0])
        subgroup = "General"
        leaf = _humanize(parts[1])
    else:
        group = "General"
        subgroup = "General"
        leaf = _humanize(parts[0])
    return group, subgroup, leaf


class SettingsViewModel:
    """ViewModel for the application Settings dialog.

    Loads all known configuration keys and their metadata from the
    ``ConfigurationService``, supports pending (uncommitted) edits,
    text filtering, and batch apply/cancel/restore-defaults.
    """

    def __init__(self, config: ConfigurationService) -> None:
        self._config = config
        self._metadata: Dict[str, Dict[str, Any]] = config.get_metadata()
        self._current_values: Dict[str, Any] = {}
        self._pending: Dict[str, Any] = {}
        self._filter_text: str = ""

        self._on_values_changed: List[Callable[[], None]] = []
        self._on_pending_changed: List[Callable[[], None]] = []

        self._reload_values()

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def add_values_changed_callback(
        self, cb: Callable[[], None],
    ) -> None:
        """Register a callback fired when values are applied or reset."""
        self._on_values_changed.append(cb)

    def add_pending_changed_callback(
        self, cb: Callable[[], None],
    ) -> None:
        """Register a callback fired when pending changes or filter update."""
        self._on_pending_changed.append(cb)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def filtered_grouped_settings(self) -> GroupedSettings:
        """Return the full settings hierarchy filtered by current text."""
        result: GroupedSettings = {}
        needle = self._filter_text.lower()

        for key, meta in self._metadata.items():
            group, subgroup, leaf = _parse_key(key)
            desc = meta.get("description", "")

            if needle and not self._matches(key, leaf, desc, needle):
                continue

            current = self.get_current_value(key)
            default = meta.get("default")
            type_str = meta.get("type", "str")
            choices = meta.get("choices", [])

            entry: SettingEntry = (
                key, leaf, type_str, current, default, desc, choices,
            )
            result.setdefault(group, {}).setdefault(
                subgroup, [],
            ).append(entry)

        return result

    def get_current_value(self, key: str) -> Any:
        """Return pending value if it exists, else the live value."""
        if key in self._pending:
            return self._pending[key]
        return self._current_values.get(key)

    @property
    def has_pending_changes(self) -> bool:
        """True when there are uncommitted edits."""
        return len(self._pending) > 0

    @property
    def all_keys(self) -> List[str]:
        """Return the list of all known configuration keys."""
        return list(self._metadata.keys())

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def set_pending(self, key: str, value: Any) -> None:
        """Record an uncommitted change for *key*."""
        self._pending[key] = value
        self._notify_pending_changed()

    def apply(self) -> None:
        """Write all pending changes to the config service."""
        for key, value in self._pending.items():
            self._config.set(key, value)
        self._pending.clear()
        self._reload_values()
        self._notify_values_changed()

    def cancel(self) -> None:
        """Discard all pending changes without writing to disk."""
        self._pending.clear()

    def restore_defaults(self) -> None:
        """Reset all keys to bundled defaults."""
        self._config.reset_to_defaults()
        self._pending.clear()
        self._reload_values()
        self._notify_values_changed()

    def filter(self, text: str) -> None:
        """Set the filter text and notify for view rebuild."""
        self._filter_text = text
        self._notify_pending_changed()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _reload_values(self) -> None:
        """Refresh current values from the config service."""
        for key, meta in self._metadata.items():
            default = meta.get("default")
            self._current_values[key] = self._config.get(key, default)

    @staticmethod
    def _matches(
        key: str, label: str, description: str, needle: str,
    ) -> bool:
        """Return True if *needle* appears in key, label, or description."""
        return (
            needle in key.lower()
            or needle in label.lower()
            or needle in description.lower()
        )

    def _notify_values_changed(self) -> None:
        for cb in self._on_values_changed:
            cb()

    def _notify_pending_changed(self) -> None:
        for cb in self._on_pending_changed:
            cb()
