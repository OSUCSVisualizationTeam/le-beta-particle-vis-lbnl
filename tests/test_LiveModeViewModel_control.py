"""Unit tests for LiveModeViewModel pause / pin / pending-intent state.

All tests are headless (no QApplication). Uses the same stubs as
test_live_mode_viewmodel.py.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
import uuid

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import (
    BatchEventCallback,
    EventCallback,
    EventHandlerInterface,
)
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.frontend.livemode.LiveModeViewModel import LiveModeViewModel


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubConfig(ConfigurationService):
    def __init__(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        self._data: Dict[str, Any] = overrides or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get_description(self, key: str) -> Optional[str]:
        return None

    def reset_to_defaults(self) -> None:
        self._data.clear()

    def get_metadata(self) -> Dict[str, Dict[str, Any]]:
        return {}


class _StubEventHandler(EventHandlerInterface):
    def __init__(self) -> None:
        self._callbacks: Dict[str, Dict[str, EventCallback]] = {}

    def register_callback(self, event_name: str, callback: EventCallback) -> str:
        cb_id = uuid.uuid4().hex
        self._callbacks.setdefault(event_name, {})[cb_id] = callback
        return cb_id

    def register_batch_callback(self, event_name: str, callback: BatchEventCallback) -> str:
        return uuid.uuid4().hex

    def unregister(self, callback_id: str) -> bool:
        for cbs in self._callbacks.values():
            if callback_id in cbs:
                del cbs[callback_id]
                return True
        return False

    def unregister_all(self, event_name: str) -> int:
        removed = len(self._callbacks.get(event_name, {}))
        self._callbacks.pop(event_name, None)
        return removed

    def dispatch(self, envelope: EventEnvelope) -> None:
        for cb in self._callbacks.get(envelope.name, {}).values():
            cb(envelope)

    def shutdown(self, timeout_ms: int = 2000) -> None:
        self._callbacks.clear()


class _StubRepository(EventRepository):
    def fetch_events(self, *a, **kw):
        return []

    def query_clusters(self, *a, **kw):
        return []

    def query_recent_clusters(self, *a, **kw):
        pass

    def query_recent_clusters_sync(self, *a, **kw):
        return []

    def query_fits(self, *a, **kw):
        pass

    def query_fits_clusters(self, *a, **kw):
        pass

    def query_fits_sync(self, *a, **kw):
        return []


def _make_cluster(cluster_id: int = 1) -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(top=6, left=0, bottom=0, right=6),
        data=np.ones((6, 6), dtype=np.float32),
        centerX=3,
        centerY=3,
        sigmaX=1.0,
        sigmaY=1.0,
        energy=1000.0,
        fitsFilename=None,
        hdu_id=None,
        date=None,
        pixelCount=36,
        clusterId=cluster_id,
        fitsId=cluster_id * 10,
    )


def _make_vm() -> LiveModeViewModel:
    return LiveModeViewModel(
        config=_StubConfig(),
        eventHandler=_StubEventHandler(),
        repository=_StubRepository(),
        physics=MagicMock(spec=PhysicsConversionManager),
    )


# ---------------------------------------------------------------------------
# Pause / unpause
# ---------------------------------------------------------------------------


def test_initial_paused_state_is_false():
    vm = _make_vm()
    assert vm.paused is False


def test_toggle_paused_flips_to_true():
    vm = _make_vm()
    vm.toggle_paused()
    assert vm.paused is True


def test_toggle_paused_flips_back_to_false():
    vm = _make_vm()
    vm.toggle_paused()
    vm.toggle_paused()
    assert vm.paused is False


def test_toggle_paused_fires_callback_with_new_value():
    vm = _make_vm()
    received: List[bool] = []
    vm.add_paused_changed_callback(received.append)

    vm.toggle_paused()
    assert received == [True]

    vm.toggle_paused()
    assert received == [True, False]


def test_advance_returns_zero_when_paused():
    vm = _make_vm()
    vm.toggle_paused()
    result = vm.advance()
    assert result == 0


# ---------------------------------------------------------------------------
# Pin / unpin
# ---------------------------------------------------------------------------


def test_initial_pinned_cluster_is_none():
    vm = _make_vm()
    assert vm.pinned_cluster is None


def test_pin_cluster_sets_pinned():
    vm = _make_vm()
    cluster = _make_cluster(1)
    vm.pin_cluster(cluster)
    assert vm.pinned_cluster is cluster


def test_pin_cluster_fires_callback():
    vm = _make_vm()
    cluster = _make_cluster(1)
    received: List[Optional[Cluster]] = []
    vm.add_pinned_changed_callback(received.append)

    vm.pin_cluster(cluster)
    assert received == [cluster]


def test_unpin_clears_pinned_cluster():
    vm = _make_vm()
    vm.pin_cluster(_make_cluster(1))
    vm.unpin()
    assert vm.pinned_cluster is None


def test_unpin_fires_callback_with_none():
    vm = _make_vm()
    vm.pin_cluster(_make_cluster(1))
    received: List[Optional[Cluster]] = []
    vm.add_pinned_changed_callback(received.append)

    vm.unpin()
    assert received == [None]


def test_unpin_when_not_pinned_is_noop():
    vm = _make_vm()
    received: List[Optional[Cluster]] = []
    vm.add_pinned_changed_callback(received.append)
    vm.unpin()
    assert received == []


# ---------------------------------------------------------------------------
# Pause clears pin
# ---------------------------------------------------------------------------


def test_unpausing_clears_pin_and_fires_both_callbacks():
    vm = _make_vm()
    cluster = _make_cluster(1)
    vm.pin_cluster(cluster)

    paused_log: List[bool] = []
    pinned_log: List[Optional[Cluster]] = []
    vm.add_paused_changed_callback(paused_log.append)
    vm.add_pinned_changed_callback(pinned_log.append)

    vm.toggle_paused()   # pause
    vm.toggle_paused()   # unpause — should clear pin

    assert vm.pinned_cluster is None
    assert False in paused_log
    assert None in pinned_log


def test_pausing_does_not_clear_pin():
    vm = _make_vm()
    cluster = _make_cluster(2)
    vm.pin_cluster(cluster)
    vm.toggle_paused()
    assert vm.pinned_cluster is cluster


# ---------------------------------------------------------------------------
# Pending intents
# ---------------------------------------------------------------------------


def test_request_open_in_historical_sets_pending_cluster():
    vm = _make_vm()
    cluster = _make_cluster(5)
    vm.request_open_in_historical(cluster)
    assert vm.pending_cluster_for_historical is cluster


def test_request_open_in_historical_clears_pin():
    vm = _make_vm()
    vm.pin_cluster(_make_cluster(1))
    pinned_log: List[Optional[Cluster]] = []
    vm.add_pinned_changed_callback(pinned_log.append)

    vm.request_open_in_historical(_make_cluster(5))

    assert vm.pinned_cluster is None
    assert None in pinned_log


def test_request_save_frame_sets_pending_fields():
    vm = _make_vm()
    cluster = _make_cluster(7)
    path = Path("/tmp/export.h5")
    vm.request_save_frame(cluster, path)

    assert vm.pending_save_cluster is cluster
    assert vm.pending_save_path == path
