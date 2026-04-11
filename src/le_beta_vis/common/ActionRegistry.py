"""Abstract action dispatch registry — **stub** for the future
actionable-error round-trip channel.

The real implementation will live behind a separate ZMQ
``REQ/REP`` channel (``event_handler:zmq_action_endpoint``):

1. The backend binds a REP socket and hosts an
   :class:`ActionRegistry` that maps ``action_name`` → handler.
2. The frontend, after the user clicks a button on an
   actionable event, constructs a REQ socket and sends
   ``{"action_name": ..., "payload": ...}``.
3. The backend's :class:`ActionRegistry` looks up the handler
   and returns its response dict.

Tracked as a follow-up GitHub issue.  Only the ABC and a safe
no-op implementation live here so the rest of the codebase can
reference the interface without guessing at its shape.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


ActionHandler = Callable[[Dict[str, Any]], Dict[str, Any]]
"""Signature of a registered action handler: takes a payload
dict and returns a response dict."""


class ActionRegistry(ABC):
    """Abstract registry of named actions that backends may
    expose and frontends may invoke.

    **Not implemented yet.**  Concrete implementations must
    land alongside the REQ/REP action channel in a follow-up
    issue.  Until then, use :class:`NoOpActionRegistry` as a
    placeholder.
    """

    @abstractmethod
    def register(self, action_name: str, handler: ActionHandler) -> None:
        """Registers an action handler under ``action_name``."""
        raise NotImplementedError

    @abstractmethod
    def dispatch(
        self,
        action_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Invokes the handler registered for ``action_name``.

        Returns:
            The handler's response dict.

        Raises:
            KeyError: If no handler is registered under the
                given name.
        """
        raise NotImplementedError


class NoOpActionRegistry(ActionRegistry):
    """Safe placeholder for the actionable-error stub.

    ``register`` succeeds silently; ``dispatch`` raises
    ``NotImplementedError`` so accidental use during the interim
    period surfaces immediately instead of silently dropping
    action invocations.
    """

    def register(self, action_name: str, handler: ActionHandler) -> None:
        return None

    def dispatch(
        self,
        action_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "NoOpActionRegistry.dispatch: action round-trip channel "
            "is not implemented yet (see follow-up issue)"
        )
