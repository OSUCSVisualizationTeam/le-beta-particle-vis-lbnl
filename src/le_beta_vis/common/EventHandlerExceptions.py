"""Exception hierarchy for the EventHandler service."""


class EventHandlerError(Exception):
    """Base class for all EventHandler-related errors."""


class QueueFullError(EventHandlerError):
    """Raised when a bounded dispatch queue is full and the overflow
    policy is ``block`` with a timeout that elapsed without room.

    Never raised for ``drop_oldest`` or ``drop_newest`` policies —
    those drop silently and increment a counter instead.
    """


class UnknownEventTypeError(EventHandlerError):
    """Raised when an operation references an event name that has
    never been registered and no dispatch queue exists for it."""


class EventHandlerShutdownError(EventHandlerError):
    """Raised when a dispatch or registration is attempted on an
    EventHandler that has already been shut down."""
