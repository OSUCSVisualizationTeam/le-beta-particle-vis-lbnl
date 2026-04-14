"""Unit tests for LiveModeViewModel.

All tests are headless (no QApplication). Uses stub implementations
for ConfigurationService, EventHandlerInterface, EventRepository,
and PhysicsConversionManager.
"""

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


def _make_cluster(energy: float = 1000.0, cluster_id: int = 0) -> Cluster:
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
        clusterId=cluster_id,
    )


class _StubRepository(EventRepository):
    """Stub EventRepository returning a fixed cluster list."""

    def __init__(self, clusters: Optional[List[Cluster]] = None) -> None:
        if clusters is not None:
            self._clusters = clusters
        else:
            self._clusters = [
                _make_cluster(500.0 + i * 100, cluster_id=i)
                for i in range(5)
            ]

    def fetch_events(self) -> List[Cluster]:
        return list(self._clusters)

    def query_clusters(self, query_filter=None) -> List[Cluster]:
        return list(self._clusters)

    def query_recent_clusters(
        self, limit: int, offset: int = 0
    ) -> List[Cluster]:
        return list(self._clusters[offset : offset + limit])


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
    return _StubConfig({
        "gui:livemode:grid_rows": 4,
        "gui:livemode:grid_columns": 5,
    })


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
# Tests — Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_creates_queue_with_capacity(self, vm: LiveModeViewModel) -> None:
        assert vm._queue.capacity == 20  # 4 rows * 5 cols

    def test_grid_shape_from_config(self, vm: LiveModeViewModel) -> None:
        assert vm.grid_shape == (4, 5)

    def test_grid_returns_queue_snapshot(self, vm: LiveModeViewModel) -> None:
        grid = vm.grid
        assert len(grid) == 20
        assert all(s is None for s in grid)

    def test_grid_snapshot_isolation(self, vm: LiveModeViewModel) -> None:
        snap = vm.grid
        snap[0] = _make_cluster()
        assert vm.grid[0] is None

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


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------


class TestActivateDeactivate:
    def test_activate_registers_callback(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        with patch.object(vm, "_schedule_refill"):
            vm.activate()
        assert "cluster.classified" in event_handler._callbacks
        assert len(event_handler._callbacks["cluster.classified"]) == 1

    def test_activate_is_idempotent(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        with patch.object(vm, "_schedule_refill"):
            vm.activate()
            vm.activate()
        assert len(event_handler._callbacks["cluster.classified"]) == 1

    def test_activate_schedules_initial_refill(
        self, vm: LiveModeViewModel,
    ) -> None:
        with patch.object(vm, "_schedule_refill") as mock_refill:
            vm.activate()
            mock_refill.assert_called_once_with(vm._capacity)

    def test_deactivate_unregisters(
        self, vm: LiveModeViewModel, event_handler: _StubEventHandler,
    ) -> None:
        with patch.object(vm, "_schedule_refill"):
            vm.activate()
        vm.deactivate()
        cbs = event_handler._callbacks.get("cluster.classified", {})
        assert len(cbs) == 0

    def test_deactivate_noop_when_inactive(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm.deactivate()  # should not raise


# ---------------------------------------------------------------------------
# Tests — Advance
# ---------------------------------------------------------------------------


class TestAdvance:
    def test_empty_queue_returns_zero(self, vm: LiveModeViewModel) -> None:
        assert vm.advance() == 0

    def test_dequeues_featured(self, vm: LiveModeViewModel) -> None:
        c = _make_cluster(2000.0, cluster_id=1)
        vm._queue.append_fallback([c])

        featured = []
        vm.add_featured_changed_callback(lambda cl: featured.append(cl))

        count = vm.advance()
        assert count == 1
        assert len(featured) == 1
        assert featured[0] is c

    def test_no_featured_callback_on_empty(
        self, vm: LiveModeViewModel,
    ) -> None:
        featured = []
        vm.add_featured_changed_callback(lambda cl: featured.append(cl))
        vm.advance()
        assert len(featured) == 0

    def test_advance_preserves_grid_length(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm._queue.append_fallback([_make_cluster(i) for i in range(20)])
        vm.advance()
        assert len(vm.grid) == 20

    def test_advance_inserts_fresh_clusters(
        self,
        vm: LiveModeViewModel,
        event_handler: _StubEventHandler,
    ) -> None:
        with patch.object(vm, "_schedule_refill"):
            vm.activate()
        callback = list(
            event_handler._callbacks["cluster.classified"].values(),
        )[0]
        envelope = EventEnvelope(
            name="cluster.classified",
            payload={
                "sigmaX": 1.5, "sigmaY": 1.5,
                "total_energy": 1000.0, "cluster_id": 42, "fits_id": 1,
            },
        )
        callback(envelope)

        vm._queue.append_fallback(
            [_make_cluster(i) for i in range(vm._capacity)],
        )

        vm.advance()

        assert vm._queue.pointer >= 1

    def test_advance_schedules_refill(self, vm: LiveModeViewModel) -> None:
        vm._queue.append_fallback([_make_cluster(1)])

        with patch.object(vm, "_schedule_refill") as mock_refill:
            vm.advance()
            mock_refill.assert_called_once()
            needed = mock_refill.call_args[0][0]
            assert needed > 0


# ---------------------------------------------------------------------------
# Tests — Data loading
# ---------------------------------------------------------------------------


class TestDataLoading:
    def test_triggers_data_loading_for_none_data(self) -> None:
        thumb = MagicMock()
        config = _StubConfig({
            "gui:livemode:grid_rows": 4,
            "gui:livemode:grid_columns": 5,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(),
            _StubPhysics(), thumbnailService=thumb,
        )
        # First cluster will be dequeued as featured; second stays in queue
        c_front = _make_cluster(1)
        c_pending = Cluster(
            boundingBox=BoundingBox(top=0, left=0, bottom=4, right=4),
            data=None,
            centerX=2,
            centerY=2,
            clusterId=2,
        )
        vm._queue.append_fallback([c_front, c_pending])

        vm.advance()

        thumb.request_cluster_data.assert_called()

    def test_skips_data_loading_when_data_present(self) -> None:
        thumb = MagicMock()
        config = _StubConfig({
            "gui:livemode:grid_rows": 4,
            "gui:livemode:grid_columns": 5,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(),
            _StubPhysics(), thumbnailService=thumb,
        )
        # All clusters have data — none should trigger loading
        vm._queue.append_fallback(
            [_make_cluster(i) for i in range(3)],
        )

        vm.advance()

        thumb.request_cluster_data.assert_not_called()

    def test_callback_sets_data_and_notifies(
        self, vm: LiveModeViewModel,
    ) -> None:
        c = _make_cluster(1)
        c.data = None

        grid_changed = []
        vm.add_grid_changed_callback(lambda: grid_changed.append(True))

        data = np.ones((4, 4), dtype=np.float32)
        vm._on_cluster_data_loaded(c, data)

        assert c.data is data
        assert len(grid_changed) == 1

    def test_callback_ignores_none_data(
        self, vm: LiveModeViewModel,
    ) -> None:
        c = _make_cluster(1)
        original = c.data

        vm._on_cluster_data_loaded(c, None)

        assert c.data is original


# ---------------------------------------------------------------------------
# Tests — Refill
# ---------------------------------------------------------------------------


class TestRefill:
    def test_refill_worker_appends_fallback(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm._refill_worker(5)

        snap = vm._queue.snapshot()
        filled = [s for s in snap if s is not None]
        assert len(filled) == 5

    def test_refill_in_progress_prevents_duplicates(
        self, vm: LiveModeViewModel,
    ) -> None:
        with vm._refill_lock:
            vm._refill_in_progress = True

        vm._schedule_refill(5)
        # Should not spawn a new thread — just return

    def test_refill_resets_flag_on_completion(
        self, vm: LiveModeViewModel,
    ) -> None:
        vm._refill_in_progress = False
        vm._refill_worker(3)
        assert not vm._refill_in_progress

    def test_refill_resets_flag_on_error(self) -> None:
        repo = MagicMock()
        repo.query_recent_clusters.side_effect = RuntimeError("fail")
        config = _StubConfig({
            "gui:livemode:grid_rows": 4,
            "gui:livemode:grid_columns": 5,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), repo, _StubPhysics(),
        )
        vm._refill_in_progress = True
        vm._refill_worker(3)
        assert not vm._refill_in_progress

    def test_refill_notifies_grid_changed(
        self, vm: LiveModeViewModel,
    ) -> None:
        fired = []
        vm.add_grid_changed_callback(lambda: fired.append(True))

        vm._refill_worker(3)

        assert len(fired) >= 1


# ---------------------------------------------------------------------------
# Tests — Configuration properties
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_colormap_default_inferno(self, vm: LiveModeViewModel) -> None:
        from le_beta_vis.frontend.fitsconverters.interface import Colormap
        assert vm.colormap == Colormap.INFERNO

    def test_advance_interval_default(self, vm: LiveModeViewModel) -> None:
        assert vm.advance_interval_ms == 3000

    def test_animation_duration_default(
        self, vm: LiveModeViewModel,
    ) -> None:
        assert vm.animation_duration_ms == 250

    def test_featured_size_default(self, vm: LiveModeViewModel) -> None:
        assert vm.featured_size == 320

    def test_grid_spacing_default_6(self, vm: LiveModeViewModel) -> None:
        assert vm.grid_spacing == 6

    def test_grid_spacing_minimum_clamped(self) -> None:
        config = _StubConfig({
            "gui:livemode:grid_spacing_px": 2,
            "gui:livemode:grid_rows": 2,
            "gui:livemode:grid_columns": 10,
        })
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


# ---------------------------------------------------------------------------
# Tests — Observer callbacks
# ---------------------------------------------------------------------------


class TestCallbacks:
    def test_grid_changed_callback(self, vm: LiveModeViewModel) -> None:
        calls = []
        vm.add_grid_changed_callback(lambda: calls.append(True))
        vm._notify_grid_changed()
        assert len(calls) == 1

    def test_featured_changed_callback(
        self, vm: LiveModeViewModel,
    ) -> None:
        calls = []
        vm.add_featured_changed_callback(lambda c: calls.append(c))
        c = _make_cluster(1)
        vm._notify_featured_changed(c)
        assert len(calls) == 1
        assert calls[0] is c

    def test_request_cluster_data_without_service(
        self, vm: LiveModeViewModel,
    ) -> None:
        result = []
        vm.request_cluster_data(_make_cluster(1), lambda d: result.append(d))
        assert result == [None]

    def test_request_cluster_data_with_service(self) -> None:
        mock_service = MagicMock()
        config = _StubConfig({
            "gui:livemode:grid_rows": 2,
            "gui:livemode:grid_columns": 5,
        })
        vm = LiveModeViewModel(
            config, _StubEventHandler(), _StubRepository(),
            _StubPhysics(), thumbnailService=mock_service,
        )
        cluster = _make_cluster()
        callback = MagicMock()
        vm.request_cluster_data(cluster, callback)
        mock_service.request_cluster_data.assert_called_once_with(
            cluster, callback,
        )
