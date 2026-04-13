"""Unit tests for LiveModeViewModel.

All tests are headless (no QApplication). Uses stub implementations
for ConfigurationService, EventHandlerInterface, EventRepository,
and PhysicsConversionManager.
"""

import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

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
    """Stub ConfigurationService returning configurable defaults."""

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
    """Stub EventHandler that captures registrations."""

    def __init__(self) -> None:
        self._callbacks: Dict[str, Dict[str, EventCallback]] = {}

    def register_callback(
        self, event_name: str, callback: EventCallback,
    ) -> str:
        cb_id = uuid.uuid4().hex
        self._callbacks.setdefault(event_name, {})[cb_id] = callback
        return cb_id

    def register_batch_callback(
        self, event_name: str, callback: BatchEventCallback,
    ) -> str:
        return uuid.uuid4().hex

    def unregister(self, callback_id: str) -> bool:
        for name_cbs in self._callbacks.values():
            if callback_id in name_cbs:
                del name_cbs[callback_id]
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

    def fire(self, envelope: EventEnvelope) -> None:
        """Helper: directly invoke registered callbacks."""
        self.dispatch(envelope)


def _make_cluster(energy: float = 1000.0) -> Cluster:
    """Creates a minimal Cluster for testing."""
    data = np.ones((6, 6), dtype=np.float32) * energy / 36
    return Cluster(
        boundingBox=BoundingBox(top=0, left=0, bottom=6, right=6),
        data=data,
        centerX=3,
        centerY=3,
        sigmaX=1.5,
        sigmaY=1.5,
        energy=energy,
        pixelCount=36,
        clusterId=42,
    )


class _StubRepository(EventRepository):
    """Stub EventRepository returning a fixed cluster list."""

    def __init__(self, clusters: Optional[List[Cluster]] = None) -> None:
        if clusters is not None:
            self._clusters = clusters
        else:
            self._clusters = [_make_cluster(500.0 + i * 100) for i in range(5)]

    def fetch_events(self) -> List[Cluster]:
        return list(self._clusters)


class _StubPhysics(PhysicsConversionManager):
    """Stub PhysicsConversionManager with a fixed conversion factor."""

    @property
    def kev_conversion_factor(self) -> float:
        return 1.02857e-5

    @property
    def pedestal_width(self) -> int:
        return 1400

    def calculate_threshold(self, sigma: float) -> float:
        return sigma * self.pedestal_width

    def adu_to_kev(self, value):
        return value * self.kev_conversion_factor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> _StubConfig:
    return _StubConfig()


@pytest.fixture
def event_handler() -> _StubEventHandler:
    return _StubEventHandler()


@pytest.fixture
def repository() -> _StubRepository:
    return _StubRepository()


@pytest.fixture
def physics() -> _StubPhysics:
    return _StubPhysics()


@pytest.fixture
def vm(
    config: _StubConfig,
    event_handler: _StubEventHandler,
    repository: _StubRepository,
    physics: _StubPhysics,
) -> LiveModeViewModel:
    return LiveModeViewModel(config, event_handler, repository, physics)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestActivateDeactivate:
    """Tests for EventHandler subscription lifecycle."""

    def test_activate_registers_callback(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        vm.activate()
        assert "cluster.classified" in event_handler._callbacks
        assert len(event_handler._callbacks["cluster.classified"]) == 1

    def test_activate_is_idempotent(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        vm.activate()
        vm.activate()
        assert len(event_handler._callbacks["cluster.classified"]) == 1

    def test_deactivate_unregisters(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        vm.activate()
        vm.deactivate()
        cbs = event_handler._callbacks.get("cluster.classified", {})
        assert len(cbs) == 0

    def test_deactivate_noop_when_inactive(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm.deactivate()  # should not raise


class TestClusterFromPayload:
    """Tests for payload deserialization."""

    def test_cluster_from_payload_basic(self, vm: LiveModeViewModel) -> None:
        payload = {
            "sigmaX": 2.0,
            "sigmaY": 1.5,
            "total_energy": 5000.0,
            "classification": "TRITIUM",
            "cnn_classification": 0.95,
            "nrg_classification": 0.88,
            "bdt_classification": 0.90,
            "fits_id": 1,
            "cluster_id": 7,
        }
        cluster = vm._cluster_from_payload(payload)
        assert cluster.sigmaX == 2.0
        assert cluster.sigmaY == 1.5
        assert cluster.energy == 5000.0
        assert cluster.cnnClassification == 0.95
        assert cluster.clusterId == 7
        assert cluster.data is not None
        assert cluster.data.shape[0] > 0

    def test_cluster_from_payload_ndarray_shape(
        self, vm: LiveModeViewModel,
    ) -> None:
        payload = {"sigmaX": 3.0, "sigmaY": 2.0}
        cluster = vm._cluster_from_payload(payload)
        w = max(6, int(3.0 * 4 + 2))
        h = max(6, int(2.0 * 4 + 2))
        assert cluster.data.shape == (h, w)

    def test_cluster_from_payload_defaults(
        self, vm: LiveModeViewModel,
    ) -> None:
        cluster = vm._cluster_from_payload({})
        assert cluster.sigmaX == 1.5
        assert cluster.sigmaY == 1.5
        assert cluster.energy == 1000.0
        assert cluster.classification == "UNCLASSIFIED"


class TestAdvance:
    """Tests for grid advancement logic."""

    def test_advance_empty_is_noop(
        self, vm: LiveModeViewModel,
    ) -> None:
        count = vm.advance()
        assert count == 0
        assert all(c is None for c in vm.grid)

    def test_event_sets_featured_immediately(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        vm.activate()
        envelope = EventEnvelope(
            name="cluster.classified",
            payload={
                "sigmaX": 1.5, "sigmaY": 1.5,
                "total_energy": 2000.0,
            },
            source="test",
        )
        event_handler.fire(envelope)
        assert vm.featured is not None
        assert vm.featured.energy == 2000.0

    def test_advance_does_not_change_featured(
        self, vm: LiveModeViewModel,
    ) -> None:
        cluster = _make_cluster(3000.0)
        with vm._lock:
            vm._grid[0] = cluster
        vm.advance()
        # featured is only set by events, not by advance
        assert vm.featured is None

    def test_shift_grid_preserves_length(
        self, vm: LiveModeViewModel,
    ) -> None:
        initial_len = len(vm.grid)
        vm.advance()
        assert len(vm.grid) == initial_len

    def test_grid_snapshot_isolation(
        self, vm: LiveModeViewModel,
    ) -> None:
        snapshot = vm.grid
        snapshot[0] = _make_cluster()
        assert vm.grid[0] is None  # internal state unaffected


class TestConfiguration:
    """Tests for config-driven properties."""

    def test_colormap_default_inferno(self, vm: LiveModeViewModel) -> None:
        from le_beta_vis.frontend.fitsconverters.interface import Colormap
        assert vm.colormap == Colormap.INFERNO

    def test_grid_count_default_1000(self, vm: LiveModeViewModel) -> None:
        rows, cols = vm.grid_shape
        assert rows * cols == 1000
        assert rows == 25
        assert cols == 40

    def test_grid_count_clamped_below_20(self) -> None:
        config = _StubConfig({
            "gui:livemode:grid_rows": 1,
            "gui:livemode:grid_columns": 1,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(), _StubPhysics(),
        )
        rows, cols = vm.grid_shape
        assert rows * cols >= 20

    def test_grid_count_clamped_above_2000(self) -> None:
        config = _StubConfig({
            "gui:livemode:grid_rows": 100,
            "gui:livemode:grid_columns": 100,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(), _StubPhysics(),
        )
        rows, cols = vm.grid_shape
        assert rows * cols <= 2000

    def test_advance_interval_default(self, vm: LiveModeViewModel) -> None:
        assert vm.advance_interval_ms == 3000

    def test_animation_duration_default(self, vm: LiveModeViewModel) -> None:
        assert vm.animation_duration_ms == 400

    def test_featured_size_default(self, vm: LiveModeViewModel) -> None:
        assert vm.featured_size == 320


class TestFallback:
    """Tests for fallback data loading."""

    def test_fallback_fills_grid_from_front(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm.trigger_fallback()
        import time
        time.sleep(0.5)
        with vm._lock:
            filled = [i for i, c in enumerate(vm._grid) if c is not None]
        assert len(filled) > 0
        # Slots must be filled from index 0 forward
        assert filled == list(range(len(filled)))

    def test_fallback_sets_featured(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm.trigger_fallback()
        import time
        time.sleep(0.5)
        assert vm.featured is not None

    def test_fallback_with_empty_repository(self) -> None:
        config = _StubConfig()
        repo = _StubRepository(clusters=[])
        vm = LiveModeViewModel(
            config, _StubEventHandler(), repo, _StubPhysics(),
        )
        vm.trigger_fallback()
        import time
        time.sleep(0.5)
        with vm._lock:
            assert all(c is None for c in vm._grid)


class TestCallbacks:
    """Tests for observer notification."""

    def test_grid_changed_callback_fires(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        fired = []
        vm.add_grid_changed_callback(lambda: fired.append(True))
        vm.activate()
        envelope = EventEnvelope(
            name="cluster.classified",
            payload={"sigmaX": 1.0, "sigmaY": 1.0, "total_energy": 500.0},
            source="test",
        )
        event_handler.fire(envelope)
        assert len(fired) >= 1

    def test_featured_changed_callback_fires_on_event(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        featured_values: List[Optional[Cluster]] = []
        vm.add_featured_changed_callback(
            lambda c: featured_values.append(c),
        )
        vm.activate()
        envelope = EventEnvelope(
            name="cluster.classified",
            payload={"sigmaX": 1.0, "sigmaY": 1.0, "total_energy": 750.0},
            source="test",
        )
        event_handler.fire(envelope)
        assert len(featured_values) == 1
        assert featured_values[0].energy == 750.0

    def test_advance_does_not_fire_featured_changed(
        self, vm: LiveModeViewModel,
    ) -> None:
        featured_values: List[Optional[Cluster]] = []
        vm.add_featured_changed_callback(
            lambda c: featured_values.append(c),
        )
        cluster = _make_cluster()
        with vm._lock:
            vm._grid[0] = cluster
        vm.advance()
        assert len(featured_values) == 0

    def test_advance_fires_grid_changed(
        self, vm: LiveModeViewModel,
    ) -> None:
        fired = []
        vm.add_grid_changed_callback(lambda: fired.append(True))
        # Put a cluster in the grid so advance() doesn't short-circuit
        cluster = _make_cluster()
        with vm._lock:
            vm._grid[0] = cluster
        vm.advance()
        assert len(fired) >= 1


class TestNewConfigProperties:
    """Tests for properties added in the live mode improvements."""

    def test_grid_spacing_default_6(self, vm: LiveModeViewModel) -> None:
        assert vm.grid_spacing == 6

    def test_grid_spacing_minimum_clamped(self) -> None:
        config = _StubConfig({"gui:livemode:grid_spacing_px": 2})
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(), _StubPhysics(),
        )
        assert vm.grid_spacing >= 6

    def test_left_panel_width_pct_default(
        self, vm: LiveModeViewModel,
    ) -> None:
        assert vm.left_panel_width_pct == 0.25

    def test_histogram_min_height_pct_default(
        self, vm: LiveModeViewModel,
    ) -> None:
        assert vm.histogram_min_height_pct == 0.10


class TestRequestClusterData:
    """Tests for ThumbnailLoaderService-backed cluster data loading."""

    def test_request_without_service_calls_none(self) -> None:
        vm = LiveModeViewModel(
            _StubConfig(), _StubEventHandler(),
            _StubRepository(), _StubPhysics(),
        )
        results: List[Optional[np.ndarray]] = []
        vm.request_cluster_data(_make_cluster(), results.append)
        assert len(results) == 1
        assert results[0] is None

    def test_request_with_service_delegates(self) -> None:
        mock_service = MagicMock()
        vm = LiveModeViewModel(
            _StubConfig(), _StubEventHandler(),
            _StubRepository(), _StubPhysics(),
            thumbnailService=mock_service,
        )
        cluster = _make_cluster()
        callback = MagicMock()
        vm.request_cluster_data(cluster, callback)
        mock_service.request_cluster_data.assert_called_once_with(
            cluster, callback,
        )


class TestGaussianBlob:
    """Tests for synthetic Gaussian blob generation."""

    def test_blob_shape(self) -> None:
        blob = LiveModeViewModel._gaussian_blob(10, 8, 5, 4, 2.0, 1.5, 1000.0)
        assert blob.shape == (8, 10)
        assert blob.dtype == np.float32

    def test_blob_peak_at_center(self) -> None:
        blob = LiveModeViewModel._gaussian_blob(10, 10, 5, 5, 2.0, 2.0, 1000.0)
        peak_y, peak_x = np.unravel_index(blob.argmax(), blob.shape)
        assert peak_x == 5
        assert peak_y == 5

    def test_blob_all_positive(self) -> None:
        blob = LiveModeViewModel._gaussian_blob(8, 8, 4, 4, 1.5, 1.5, 500.0)
        assert np.all(blob >= 0)


class TestFeaturedHold:
    """Tests for featured cluster hold timer and queue deduplication."""

    def _make_envelope(self, energy: float = 1000.0) -> EventEnvelope:
        return EventEnvelope(
            name="cluster.classified",
            payload={
                "sigmaX": 1.5,
                "sigmaY": 1.5,
                "total_energy": energy,
            },
            source="test",
        )

    def test_first_event_always_featured(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        """First event becomes featured because _featured_set_at starts at 0."""
        vm.activate()
        event_handler.fire(self._make_envelope(2000.0))
        assert vm.featured is not None
        assert vm.featured.energy == 2000.0

    def test_second_event_within_hold_not_featured(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        """Events within hold period go to incoming, not featured."""
        vm.activate()
        event_handler.fire(self._make_envelope(2000.0))
        first_featured = vm.featured

        event_handler.fire(self._make_envelope(3000.0))
        assert vm.featured is first_featured
        assert vm.featured.energy == 2000.0

    def test_second_event_within_hold_queued_to_incoming(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        """Events within hold period are appended to _incoming."""
        vm.activate()
        event_handler.fire(self._make_envelope(2000.0))
        event_handler.fire(self._make_envelope(3000.0))

        with vm._lock:
            assert len(vm._incoming) == 1
            assert vm._incoming[0].energy == 3000.0

    def test_featured_cluster_not_in_incoming(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        """When a cluster becomes featured it is not in _incoming."""
        vm.activate()
        event_handler.fire(self._make_envelope(2000.0))

        with vm._lock:
            assert len(vm._incoming) == 0

    def test_event_after_hold_becomes_featured(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        """After hold period elapses, the next event replaces featured."""
        vm.activate()
        event_handler.fire(self._make_envelope(2000.0))

        # Simulate hold period elapsed by backdating _featured_set_at
        with vm._lock:
            vm._featured_set_at = time.monotonic() - 10.0

        event_handler.fire(self._make_envelope(5000.0))
        assert vm.featured is not None
        assert vm.featured.energy == 5000.0

        with vm._lock:
            assert len(vm._incoming) == 0

    def test_featured_hold_s_default(
        self, vm: LiveModeViewModel,
    ) -> None:
        assert vm.featured_hold_s == 5

    def test_featured_hold_s_clamped_below(self) -> None:
        config = _StubConfig({"gui:livemode:featured_hold_s": 1})
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(), _StubPhysics(),
        )
        assert vm.featured_hold_s >= 3

    def test_featured_hold_s_clamped_above(self) -> None:
        config = _StubConfig({"gui:livemode:featured_hold_s": 20})
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(), _StubPhysics(),
        )
        assert vm.featured_hold_s <= 10

    def test_featured_changed_callback_not_fired_during_hold(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        """Callback should not fire when featured doesn't change."""
        featured_values: List[Optional[Cluster]] = []
        vm.add_featured_changed_callback(
            lambda c: featured_values.append(c),
        )
        vm.activate()
        event_handler.fire(self._make_envelope(2000.0))
        assert len(featured_values) == 1

        event_handler.fire(self._make_envelope(3000.0))
        assert len(featured_values) == 1  # no second callback

    def test_fallback_resets_featured_set_at(
        self, vm: LiveModeViewModel,
    ) -> None:
        """Fallback should set _featured_set_at so post-fallback events
        respect the hold period."""
        vm.trigger_fallback()
        time.sleep(0.5)

        assert vm.featured is not None
        with vm._lock:
            assert vm._featured_set_at > 0.0


class TestBatchDrainAdvance:
    """Tests for batch-drain advance behavior."""

    def test_advance_returns_zero_when_empty_grid(
        self, vm: LiveModeViewModel,
    ) -> None:
        assert vm.advance() == 0

    def test_advance_returns_one_when_no_incoming_but_grid_has_content(
        self, vm: LiveModeViewModel,
    ) -> None:
        with vm._lock:
            vm._grid[0] = _make_cluster(500.0)
        assert vm.advance() == 1

    def test_advance_drains_single_item(
        self, vm: LiveModeViewModel,
    ) -> None:
        with vm._lock:
            vm._incoming.append(_make_cluster(1000.0))
        count = vm.advance()
        assert count == 1
        grid = vm.grid
        assert grid[-1] is not None
        assert grid[-1].energy == 1000.0

    def test_advance_drains_multiple_items(
        self, vm: LiveModeViewModel,
    ) -> None:
        clusters = [_make_cluster(100.0 * (i + 1)) for i in range(5)]
        with vm._lock:
            for c in clusters:
                vm._incoming.append(c)
        count = vm.advance()
        assert count == 5
        grid = vm.grid
        # Last 5 positions should have the batch
        for i in range(5):
            assert grid[-(5 - i)] is not None
            assert grid[-(5 - i)].energy == clusters[i].energy

    def test_advance_preserves_grid_length_after_batch(
        self, vm: LiveModeViewModel,
    ) -> None:
        initial_len = len(vm.grid)
        with vm._lock:
            for i in range(10):
                vm._incoming.append(_make_cluster(float(i)))
        vm.advance()
        assert len(vm.grid) == initial_len

    def test_advance_caps_drain_at_capacity(self) -> None:
        """Drain never exceeds grid capacity even with oversized queue."""
        config = _StubConfig({
            "gui:livemode:grid_rows": 4,
            "gui:livemode:grid_columns": 5,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(), _StubPhysics(),
        )
        capacity = 4 * 5  # 20 (meets min grid count)
        with vm._lock:
            for i in range(35):
                vm._incoming.append(_make_cluster(float(i)))
        count = vm.advance()
        assert count == capacity
        # Remaining items stay in _incoming
        with vm._lock:
            assert len(vm._incoming) == 15

    def test_advance_shifts_grid_correctly(
        self, vm: LiveModeViewModel,
    ) -> None:
        """Grid should drop first N items and append the batch."""
        # Prefill grid with identifiable clusters
        with vm._lock:
            for i in range(len(vm._grid)):
                vm._grid[i] = _make_cluster(float(i))
            # Queue 3 new clusters
            for j in range(3):
                vm._incoming.append(_make_cluster(9000.0 + j))
        count = vm.advance()
        assert count == 3
        grid = vm.grid
        # First items should be what was at indices 3..end of old grid
        assert grid[0].energy == 3.0
        # Last 3 should be the new batch
        assert grid[-3].energy == 9000.0
        assert grid[-2].energy == 9001.0
        assert grid[-1].energy == 9002.0

    def test_advance_empty_incoming_inserts_none_at_tail(
        self, vm: LiveModeViewModel,
    ) -> None:
        """When incoming is empty, shift by 1 and insert None at tail."""
        with vm._lock:
            vm._grid[-1] = _make_cluster(500.0)
        count = vm.advance()
        assert count == 1
        assert vm.grid[-1] is None
