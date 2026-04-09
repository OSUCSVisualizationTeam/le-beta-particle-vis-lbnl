"""Abstract interface for the EventHandler pub/sub dispatcher.

The EventHandler is the single entry point for backend → frontend
push messaging.  It receives :class:`EventEnvelope` objects
(typically from a transport such as :class:`ZMQEventHandlerSource`),
routes them to registered callbacks by event name, and dispatches
asynchronously on per-event-type worker threads so slow handlers
for one event type cannot block another.

Concrete implementations must honor three guarantees:

1. **Ordering per event name.** Handlers registered for the same
   event name see envelopes in the order they were dispatched.
2. **Isolation between event names.** A slow or crashing handler
   for one event name must not affect delivery of other names.
3. **Exception safety.** A handler raising is logged and the
   worker continues.  One bad callback does not stop the bus.
"""

from abc import ABC, abstractmethod
from typing import Callable, List

from .EventEnvelope import EventEnvelope


EventCallback = Callable[[EventEnvelope], None]
"""Single-envelope callback signature."""

BatchEventCallback = Callable[[List[EventEnvelope]], None]
"""Batched-delivery callback signature, used when an event name
has a non-zero coalesce window configured."""


class EventHandlerInterface(ABC):
    """Abstract interface for the EventHandler service.

    Concrete implementations own the dispatch threads and callback
    registry.  Callers interact only through this interface so the
    underlying implementation can be swapped in tests or replaced
    with a different concurrency model in the future.
    """

    @abstractmethod
    def register_callback(
        self,
        event_name: str,
        callback: EventCallback,
    ) -> str:
        """Registers a callback for ``event_name``.

        Args:
            event_name: The event name to subscribe to.
            callback: A function taking one ``EventEnvelope``.

        Returns:
            A UUID string that can be passed to :meth:`unregister`
            to remove this specific callback.
        """
        raise NotImplementedError

    @abstractmethod
    def register_batch_callback(
        self,
        event_name: str,
        callback: BatchEventCallback,
    ) -> str:
        """Registers a batched-delivery callback for ``event_name``.

        Batched callbacks receive a list of envelopes collected over
        the event's configured coalesce window.  If no coalesce
        window is configured, each batch contains exactly one
        envelope (equivalent to :meth:`register_callback`).

        Args:
            event_name: The event name to subscribe to.
            callback: A function taking a list of envelopes.

        Returns:
            A UUID string for :meth:`unregister`.
        """
        raise NotImplementedError

    @abstractmethod
    def unregister(self, callback_id: str) -> bool:
        """Removes a previously registered callback by its UUID.

        Args:
            callback_id: The UUID returned by
                :meth:`register_callback` or
                :meth:`register_batch_callback`.

        Returns:
            ``True`` if a callback was found and removed,
            ``False`` if no callback with that UUID exists.
        """
        raise NotImplementedError

    @abstractmethod
    def unregister_all(self, event_name: str) -> int:
        """Removes all callbacks registered for ``event_name``.

        Args:
            event_name: The event name whose callbacks to clear.

        Returns:
            The number of callbacks removed.
        """
        raise NotImplementedError

    @abstractmethod
    def dispatch(self, envelope: EventEnvelope) -> None:
        """Enqueues an envelope for asynchronous delivery.

        This is non-blocking under the default ``drop_oldest``
        policy.  Callers on the transport recv thread (e.g.
        :class:`ZMQEventHandlerSource`) invoke this method.

        Args:
            envelope: The envelope to deliver.
        """
        raise NotImplementedError

    @abstractmethod
    def shutdown(self, timeout_ms: int = 2000) -> None:
        """Stops all worker threads and clears the registry.

        After shutdown, further :meth:`dispatch` or registration
        calls raise :class:`EventHandlerShutdownError`.

        Args:
            timeout_ms: Maximum total time to wait joining workers.
        """
        raise NotImplementedError
