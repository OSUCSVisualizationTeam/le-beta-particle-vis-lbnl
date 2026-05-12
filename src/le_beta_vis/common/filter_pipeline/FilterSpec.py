"""Declarative metadata for Interactive Filter Stack filter types.

A filter type declares one :class:`FilterSpec` (typically as a class
attribute named ``SPEC``) and one :class:`ParameterSpec` per
user-tunable parameter. The IFS UI reads the spec at render time to:

- label each parameter with its display name (e.g. ``σ`` rather than
  ``sigma``);
- pick the right editor widget (slider+spinbox for bounded floats,
  scientific-notation entry for unbounded floats, combobox for enums);
- clamp values to declared bounds before mutating the filter instance.

Specs are immutable; create a new spec rather than mutating an existing
one. See ``project_filter_registry_side_chat.md`` for the longer-term
direction (filter discovery from a shared library).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Sequence


class ParameterType(str, Enum):
    """Coarse value category for parameter editors."""

    FLOAT = "float"
    INT = "int"
    ENUM = "enum"


class UIHint(str, Enum):
    """Optional override for the editor-widget picker.

    The default ``AUTO`` is the right choice for almost all parameters —
    the editor is picked from value bounds and type. Override only when
    the auto choice is wrong for a specific parameter.
    """

    AUTO = "auto"
    SLIDER_ONLY = "slider_only"
    SPINBOX_ONLY = "spinbox_only"
    COMPOSE = "compose"


@dataclass(frozen=True)
class ParameterSpec:
    """Declarative metadata for one filter parameter.

    Describes the value, not the widget. The UI inspects bounds + type
    to choose the right editor. ``ui_hint`` is the escape hatch when the
    auto-pick is wrong.
    """

    name: str
    label: str
    type: ParameterType = ParameterType.FLOAT
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    default: Any = 0.0
    scale: str = "linear"
    units: Optional[str] = None
    ui_hint: UIHint = UIHint.AUTO
    enum_values: Optional[Sequence[str]] = None

    def clamp(self, value: Any) -> Any:
        """Return *value* clamped to declared bounds.

        Enums and parameters without bounds pass through unchanged.
        Numeric types are coerced (``float`` or ``int``) before
        clamping so spinbox / text-entry results are normalised.
        """
        if self.type == ParameterType.ENUM:
            return value
        coerced: Any
        if self.type == ParameterType.INT:
            coerced = int(value)
        else:
            coerced = float(value)
        if self.min_value is not None and coerced < self.min_value:
            coerced = (
                int(self.min_value)
                if self.type == ParameterType.INT
                else float(self.min_value)
            )
        if self.max_value is not None and coerced > self.max_value:
            coerced = (
                int(self.max_value)
                if self.type == ParameterType.INT
                else float(self.max_value)
            )
        return coerced


@dataclass(frozen=True)
class FilterSpec:
    """Declarative metadata for one filter type.

    A filter class typically exposes its spec as the class attribute
    ``SPEC`` so the UI can introspect via ``entry.filter.SPEC`` without
    a registry lookup. ``filter_class`` is the constructor the UI calls
    when the user picks this type from the Add Filter menu.

    ``pinned`` marks structural filters whose presence is required by the
    pipeline (ADU→keV conversion, scaling preset, windowing, colormap).
    Pinned filters are seeded by the ViewModel, cannot be deleted by the
    user, and are excluded from the Add Filter menu.
    """

    type_id: str
    display_name: str
    parameters: List[ParameterSpec] = field(default_factory=list)
    filter_class: Optional[type] = None
    pinned: bool = False
