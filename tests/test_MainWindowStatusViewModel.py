"""Tests for MainWindowStatusViewModel — pure Python, no QApplication."""

from __future__ import annotations

import time
from typing import Callable, Dict, List

import pytest

from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import (
    EventCallback,
    EventHandlerInterface,
)
from le_beta_vis.frontend.viewmodels.MainWindowStatusViewModel import (
    MainWindowStatusViewModel,
    Severity,
)


# ------------------------------------------------------------------
# Fake EventHandler that invokes callbacks synchronously
# ------------------------------------------------------------------


class _FakeEventHandler(EventHandlerInterface):
    """In-process stand-in for EventHandler. Dispatch is synchronous."""

    def __init__(self) -> None:
        self._cbs: Dict[str, Dict[str, EventCallback]] = {}
        self._next_id = 0

    def register_callback(
        self, event_name: str, callback: EventCallback
    ) -> str:
        self._next_id += 1
        cb_id = f"cb-{self._next_id}"
        self._cbs.setdefault(event_name, {})[cb_id] = callback
        return cb_id

    def register_batch_callback(self, event_name, callback):  # noqa: D401
        raise NotImplementedError

    def unregister(self, callback_id: str) -> bool:
        for bucket in self._cbs.values():
            if callback_id in bucket:
                del bucket[callback_id]
                return True
        return False

    def unregister_all(self, event_name: str) -> int:
        bucket = self._cbs.pop(event_name, {})
        return len(bucket)

    def dispatch(self, envelope: EventEnvelope) -> None:
        for cb in list(self._cbs.get(envelope.name, {}).values()):
            cb(envelope)

    def shutdown(self, timeout_ms: int = 2000) -> None:
        self._cbs.clear()


@pytest.fixture
def handler() -> _FakeEventHandler:
    return _FakeEventHandler()


@pytest.fixture
def vm(handler: _FakeEventHandler) -> MainWindowStatusViewModel:
    model = MainWindowStatusViewModel(handler, clear_timeout_s=0)
    yield model
    model.shutdown()


def _wait_until(
    predicate: Callable[[], bool], timeout: float = 1.0
) -> None:
    """Poll ``predicate`` until true or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("predicate never became true")


# ------------------------------------------------------------------
# Event routing
# ------------------------------------------------------------------


class TestEventRouting:
    @pytest.mark.parametrize(
        ("event_name", "expected"),
        [
            ("log.info", Severity.INFO),
            ("log.warning", Severity.WARNING),
            ("log.error", Severity.ERROR),
            ("log.critical", Severity.ERROR),
        ],
    )
    def test_log_events_set_message_and_severity(
        self,
        handler: _FakeEventHandler,
        vm: MainWindowStatusViewModel,
        event_name: str,
        expected: Severity,
    ) -> None:
        calls: List[None] = []
        vm.add_message_changed_callback(lambda: calls.append(None))

        handler.dispatch(
            EventEnvelope(
                name=event_name,
                payload={"message": "hello world", "level": "INFO"},
            )
        )

        assert vm.message == "hello world"
        assert vm.severity is expected
        assert len(calls) == 1

    def test_log_debug_is_ignored(
        self,
        handler: _FakeEventHandler,
        vm: MainWindowStatusViewModel,
    ) -> None:
        calls: List[None] = []
        vm.add_message_changed_callback(lambda: calls.append(None))

        handler.dispatch(
            EventEnvelope(
                name="log.debug",
                payload={"message": "noisy", "level": "DEBUG"},
            )
        )

        assert vm.message == ""
        assert vm.severity is Severity.NONE
        assert calls == []

    def test_empty_message_is_ignored(
        self,
        handler: _FakeEventHandler,
        vm: MainWindowStatusViewModel,
    ) -> None:
        handler.dispatch(
            EventEnvelope(name="log.info", payload={"message": "   "})
        )
        assert vm.message == ""

    def test_shutdown_unregisters_subscriptions(
        self,
        handler: _FakeEventHandler,
    ) -> None:
        model = MainWindowStatusViewModel(handler, clear_timeout_s=0)
        model.shutdown()

        handler.dispatch(
            EventEnvelope(name="log.info", payload={"message": "late"})
        )

        assert model.message == ""


# ------------------------------------------------------------------
# Direct message API
# ------------------------------------------------------------------


class TestSetMessage:
    def test_clear_message_resets_severity(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        vm.set_message("boom", Severity.ERROR)
        vm.clear_message()
        assert vm.message == ""
        assert vm.severity is Severity.NONE

    def test_empty_text_forces_none_severity(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        vm.set_message("", Severity.ERROR)
        assert vm.severity is Severity.NONE


# ------------------------------------------------------------------
# Progress lifecycle
# ------------------------------------------------------------------


class TestProgressLifecycle:
    def test_begin_returns_unique_tokens(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        a = vm.begin_progress("Exporting A")
        b = vm.begin_progress("Exporting B")
        assert a != b
        tokens = {snap.token for snap in vm.active_progress}
        assert tokens == {a, b}

    def test_update_unknown_token_is_noop(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        vm.update_progress("does-not-exist", 0.5, "step")
        assert vm.active_progress == []

    def test_update_mutates_existing_snapshot(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        token = vm.begin_progress("Classifying")
        vm.update_progress(token, 0.42, message="frame 7")
        snap = next(s for s in vm.active_progress if s.token == token)
        assert snap.fraction == pytest.approx(0.42)
        assert snap.message == "frame 7"

    def test_end_removes_token(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        token = vm.begin_progress("Prefetching")
        vm.end_progress(token)
        assert vm.active_progress == []

    def test_end_unknown_token_is_noop(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        vm.end_progress("nope")  # must not raise

    def test_progress_callback_fires(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        calls: List[None] = []
        vm.add_progress_changed_callback(lambda: calls.append(None))
        token = vm.begin_progress("x")
        vm.update_progress(token, 0.5)
        vm.end_progress(token)
        assert len(calls) == 3


# ------------------------------------------------------------------
# Cancel
# ------------------------------------------------------------------


class TestCancel:
    def test_cancel_fires_registered_callbacks(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        token = vm.begin_progress("Exporting", cancelable=True)
        fired: List[None] = []
        vm.add_cancel_callback(token, lambda: fired.append(None))
        vm.request_cancel(token)
        assert len(fired) == 1

    def test_cancel_noncancelable_ignored(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        token = vm.begin_progress("Classifying", cancelable=False)
        fired: List[None] = []
        vm.add_cancel_callback(token, lambda: fired.append(None))
        vm.request_cancel(token)
        assert fired == []

    def test_cancel_unknown_token_is_noop(
        self, vm: MainWindowStatusViewModel
    ) -> None:
        vm.request_cancel("missing")


# ------------------------------------------------------------------
# Auto-clear timer
# ------------------------------------------------------------------


class TestAutoClear:
    def test_timeout_clears_message(
        self, handler: _FakeEventHandler
    ) -> None:
        model = MainWindowStatusViewModel(handler, clear_timeout_s=0.05)
        try:
            model.set_message("stale", Severity.INFO)
            _wait_until(lambda: model.message == "", timeout=1.0)
            assert model.severity is Severity.NONE
        finally:
            model.shutdown()

    def test_zero_timeout_disables_autoclear(
        self, handler: _FakeEventHandler
    ) -> None:
        model = MainWindowStatusViewModel(handler, clear_timeout_s=0)
        try:
            model.set_message("persist", Severity.INFO)
            time.sleep(0.1)
            assert model.message == "persist"
        finally:
            model.shutdown()

    def test_new_message_resets_timer(
        self, handler: _FakeEventHandler
    ) -> None:
        model = MainWindowStatusViewModel(handler, clear_timeout_s=0.1)
        try:
            model.set_message("first", Severity.INFO)
            time.sleep(0.05)
            model.set_message("second", Severity.INFO)
            time.sleep(0.07)
            assert model.message == "second"
            _wait_until(lambda: model.message == "", timeout=1.0)
        finally:
            model.shutdown()
