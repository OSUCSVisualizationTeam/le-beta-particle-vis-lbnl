"""Abstract publisher interface for the EventHandler bus.

The client is the *producer* side of the EventHandler pipeline.
Concrete implementations (starting with :class:`ZMQEventHandlerClient`)
serialize :class:`EventEnvelope` objects to a transport and push
them out to one or more subscribers.

Keeping this as an ABC lets the same producer code path (the
classifier, logging handler, smoke-test script) target any
future transport — WebSocket, in-proc test bus, etc. — with no
changes.
"""

from abc import ABC, abstractmethod

from .EventEnvelope import EventEnvelope


class EventHandlerClient(ABC):
    """Abstract publisher for the EventHandler bus.

    Implementations must be safe to call from multiple threads
    (the classifier may publish concurrently with the logging
    handler that wraps the same client).
    """

    @abstractmethod
    def publish(self, envelope: EventEnvelope) -> None:
        """Publishes an envelope to the transport.

        Non-blocking on best-effort transports such as
        ZMQ PUB.  Implementations must not raise on transient
        failures (e.g. a SUB reconnecting) — they should log and
        swallow so callers (especially
        :class:`ZMQEventLoggingHandler`) cannot create recursive
        failure loops.

        Args:
            envelope: The event to publish.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Releases any resources held by the client.

        Idempotent.  After close, :meth:`publish` is a no-op or
        raises, at the implementation's discretion.
        """
        raise NotImplementedError
