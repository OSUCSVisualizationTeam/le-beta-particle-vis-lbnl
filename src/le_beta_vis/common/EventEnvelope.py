"""Wire format for the EventHandler pub/sub transport.

Every message that flows through the EventHandler — cluster
notifications, forwarded log records, actionable errors —
is wrapped in an :class:`EventEnvelope`.  The envelope is
transport-agnostic: the same dataclass is serialized to JSON
for ZMQ today and could be used for any future transport
(WebSocket, in-proc test bus, etc.).

The ZMQ transport frames an envelope as a two-part message:
``[topic_bytes, envelope_json_bytes]``, where ``topic_bytes``
is ``envelope.name.encode("utf-8")``.  This lets SUB sockets
use cheap prefix filtering before deserialization.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    """Returns an ISO-8601 UTC timestamp with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _new_event_id() -> str:
    """Returns a new hex-encoded UUID4 for use as an envelope id."""
    return uuid.uuid4().hex


@dataclass(frozen=True)
class EventEnvelope:
    """A single named event flowing through the EventHandler bus.

    Attributes:
        name: Hierarchical event name (e.g. ``"cluster.classified"``,
            ``"log.error"``).  Used as the ZMQ topic frame and for
            callback routing.
        payload: Arbitrary JSON-serializable payload.  The schema is
            defined per-event-name by the producer.
        id: Unique identifier for this envelope.  Defaults to a fresh
            UUID4 hex string.
        timestamp: ISO-8601 UTC timestamp.  Defaults to the current
            wall-clock time at construction.
        source: Free-form identifier of the producing component
            (e.g. ``"eps.classifier"``, ``"frontend.main"``).
        schema: Envelope schema version.  Bump if the envelope layout
            ever changes; consumers should check this and refuse
            unknown versions.
        actionable: Optional metadata for actionable-error events.
            Always ``None`` in the current schema — reserved for the
            future actionable-error round-trip channel.
    """

    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_event_id)
    timestamp: str = field(default_factory=_utc_now_iso)
    source: str = ""
    schema: int = SCHEMA_VERSION
    actionable: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("EventEnvelope.name must be a non-empty string")
        if not isinstance(self.payload, dict):
            raise TypeError(
                f"EventEnvelope.payload must be a dict, "
                f"got {type(self.payload).__name__}"
            )
        if self.schema != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported EventEnvelope schema version {self.schema}; "
                f"expected {SCHEMA_VERSION}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Returns the envelope as a plain JSON-serializable dict."""
        return asdict(self)

    def to_json_bytes(self) -> bytes:
        """Serializes the envelope to UTF-8 JSON bytes for transport."""
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    def topic_bytes(self) -> bytes:
        """Returns the ZMQ topic frame for this envelope.

        The topic is the event name encoded as UTF-8, used as the
        first frame of a ZMQ multipart message so SUB sockets can
        filter by prefix without deserializing the payload.
        """
        return self.name.encode("utf-8")

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "EventEnvelope":
        """Reconstructs an ``EventEnvelope`` from a plain dict.

        Raises:
            ValueError: If required fields are missing or the schema
                version is unknown.
            TypeError: If field types do not match.
        """
        if "name" not in d:
            raise ValueError("EventEnvelope dict missing required field 'name'")
        return EventEnvelope(
            name=d["name"],
            payload=d.get("payload", {}) or {},
            id=d.get("id") or _new_event_id(),
            timestamp=d.get("timestamp") or _utc_now_iso(),
            source=d.get("source", ""),
            schema=int(d.get("schema", SCHEMA_VERSION)),
            actionable=d.get("actionable"),
        )

    @staticmethod
    def from_json_bytes(b: bytes) -> "EventEnvelope":
        """Parses an envelope from UTF-8 JSON bytes.

        Raises:
            ValueError: On invalid JSON or missing required fields.
        """
        try:
            data = json.loads(b.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid EventEnvelope JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"EventEnvelope JSON must decode to an object, "
                f"got {type(data).__name__}"
            )
        return EventEnvelope.from_dict(data)
