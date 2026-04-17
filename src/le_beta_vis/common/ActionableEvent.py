"""Data shapes for actionable-error events.

This module defines the *stable* dataclasses that will eventually
carry actionable errors across the EventHandler bus.  The full
round-trip (backend pushes an actionable error → frontend renders
buttons from the action descriptors → user clicks a button →
frontend invokes the named action on a separate REQ/REP channel
→ backend runs the handler and returns a response) is tracked
as a follow-up issue; none of that machinery lives here.

Keeping the shapes stable now means Troy can start emitting
actionable events through :class:`EventHandlerClient.publish`
at any time by setting :attr:`EventEnvelope.actionable` on a
normal envelope — today it will simply be dispatched to
callbacks and ignored, and later, when the real machinery
lands, those same events will route correctly.
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ActionDescriptor:
    """A single user-invocable action attached to an actionable event.

    Attributes:
        label: Human-readable button text.  The frontend View is
            responsible for running this through ``tr()`` for
            localization.
        action_name: Opaque routing key the backend will use to
            dispatch the action when the user clicks this button.
        payload_schema: Optional JSON-schema-ish dict describing
            what payload (if any) the action expects.  Reserved
            for future use; today ``None`` is fine.
    """

    label: str
    action_name: str
    payload_schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ActionDescriptor":
        return ActionDescriptor(
            label=str(d["label"]),
            action_name=str(d["action_name"]),
            payload_schema=d.get("payload_schema"),
        )


@dataclass(frozen=True)
class ActionableEvent:
    """Payload shape for an actionable-error event.

    This is *not* an :class:`EventEnvelope` — it is the object
    that a producer stores in ``envelope.actionable`` when the
    envelope represents something the user can act on.

    Attributes:
        event_id: Unique id for this actionable instance.  The
            frontend View uses this to correlate the user's
            response with the original event.
        name: Canonical action-category name (e.g.
            ``"eps.crash_recovery"``).
        message: Plain text description shown to the user.
        severity: One of ``"info"``, ``"warning"``, ``"error"``,
            ``"critical"``.
        actions: Ordered list of :class:`ActionDescriptor`
            choices.  The first entry is conventionally the
            default / recommended action.
    """

    event_id: str
    name: str
    message: str
    severity: str = "warning"
    actions: List[ActionDescriptor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "message": self.message,
            "severity": self.severity,
            "actions": [action.to_dict() for action in self.actions],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "ActionableEvent":
        return ActionableEvent(
            event_id=str(d["event_id"]),
            name=str(d["name"]),
            message=str(d["message"]),
            severity=str(d.get("severity", "warning")),
            actions=[
                ActionDescriptor.from_dict(a) for a in d.get("actions", [])
            ],
        )
