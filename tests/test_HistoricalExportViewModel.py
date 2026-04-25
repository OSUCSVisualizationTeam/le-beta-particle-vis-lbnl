# Verify gating (preset=='all' blocks, window>max blocks), export lifecycle,
# and filter-bar export-lock coordination

"""Tests for HistoricalExportViewModel."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.Colormap import Colormap
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.export.ClusterExportService import (
    ClusterExportService,
    ClusterMetadataLabels,
)
from le_beta_vis.export.ExportStorageService import (
    CancelToken,
    ExportProvenance,
    ExportStorageService,
)
from le_beta_vis.export.HistoricalExportService import HistoricalExportService
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService
from le_beta_vis.frontend.viewmodels.HistoricalExportViewModel import (
    HistoricalExportViewModel,
)
from le_beta_vis.frontend.viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)

from mock_configuration_service import MockConfigurationService


class _FakePhysics:
    kev_conversion_factor = 1.02857e-5
    pedestal_width = 1400

    def calculate_threshold(self, sigma):
        return sigma * self.pedestal_width

    def adu_to_kev(self, value):
        return value * self.kev_conversion_factor


class _NoopRepo(EventRepository):
    def fetch_events(self, callback, on_error):
        callback([])

    def query_clusters(self, query_filter, callback, on_error):
        callback([])

    def query_recent_clusters(self, limit, offset, callback, on_error):
        callback([])


class _NoopStorage(ExportStorageService):
    def write(self, out_path, clusters, provenance, cancel_token, on_progress=None):
        out_path.write_bytes(b"h5")


class _NoopPNG(ClusterExportService):
    def export(self, cluster, out_path, *, context, colormap):
        out_path.write_bytes(b"png")

    def render_metadata(self, canvas, metadata, labels):
        pass


class _NoopThumbnails(ThumbnailLoaderService):
    def request_thumbnail(self, key, cluster, on_ready):
        pass

    def clear(self):
        pass

    def evict(self, keep_keys):
        pass

    def get_cached(self, key):
        return None

    def request_cluster_data(self, cluster, on_ready):
        on_ready(None)

    def shutdown(self):
        pass


def _build_vm(
    max_window_days: Optional[int] = None,
) -> tuple[HistoricalExportViewModel, HistoricalFilterBarViewModel]:
    cfg = MockConfigurationService()
    if max_window_days is not None:
        cfg.set("gui:export:max_time_window_days", max_window_days)
    physics = _FakePhysics()
    filter_bar = HistoricalFilterBarViewModel(cfg, physics)
    svc = HistoricalExportService(_NoopRepo(), _NoopStorage(), _NoopPNG(), physics, _NoopThumbnails())
    vm = HistoricalExportViewModel(cfg, physics, svc, filter_bar)
    return vm, filter_bar


class TestGating:
    def test_blocks_when_preset_is_all(self):
        vm, fb = _build_vm()
        fb.apply_time_preset("all")
        ok, reason = vm.gating_reason()
        assert not ok
        assert "all" in reason

    def test_allows_for_24h_preset(self):
        vm, fb = _build_vm()
        fb.apply_time_preset("24h")
        assert vm.can_export() is True

    def test_blocks_custom_window_exceeding_max_days(self):
        vm, fb = _build_vm(max_window_days=30)
        fb.time_preset = "custom"
        fb.start_datetime = datetime(2026, 1, 1)
        fb.end_datetime = datetime(2026, 3, 1)  # ~59 days
        ok, reason = vm.gating_reason()
        assert not ok
        assert "30" in reason

    def test_allows_custom_window_within_max_days(self):
        vm, fb = _build_vm(max_window_days=30)
        fb.time_preset = "custom"
        fb.start_datetime = datetime(2026, 4, 1)
        fb.end_datetime = datetime(2026, 4, 20)
        assert vm.can_export() is True


class TestExportLifecycle:
    def test_export_toggles_state_and_filter_lock(self, tmp_path):
        vm, fb = _build_vm()
        states: List[bool] = []
        locks: List[bool] = []
        completions: List[Path] = []
        vm.add_state_changed_callback(states.append)
        fb.add_export_running_callback(locks.append)
        vm.add_complete_callback(completions.append)

        out = tmp_path / "out.h5"
        vm.export(out, ClusterQueryFilter())

        # Give the worker thread a moment to finish.
        import time

        for _ in range(50):
            if completions:
                break
            time.sleep(0.02)

        assert states[0] is True
        assert locks[0] is True
        assert vm.is_exporting is False  # finished
        assert fb.is_export_running is False

    def test_export_noop_while_already_exporting(self, tmp_path):
        vm, fb = _build_vm()
        vm._is_exporting = True
        before = vm._cancel_token
        vm.export(tmp_path / "x.h5", ClusterQueryFilter())
        # No new cancel token allocated; second call is a no-op.
        assert vm._cancel_token is before

    def test_cancel_resets_state_and_fires_callback(self, tmp_path):
        vm, fb = _build_vm()
        states: List[bool] = []
        locks: List[bool] = []
        cancelled: List[bool] = []
        vm.add_state_changed_callback(states.append)
        fb.add_export_running_callback(locks.append)
        vm.add_cancelled_callback(lambda: cancelled.append(True))

        def fake_run_async(request, token, **kwargs):
            cb = kwargs.get("on_cancelled")
            if cb is not None:
                cb()

            class _Dummy:
                def join(self, timeout=None):
                    pass

                def is_alive(self):
                    return False

            return _Dummy()

        vm._service.run_async = fake_run_async
        vm.export(tmp_path / "out.h5", ClusterQueryFilter())

        assert vm.is_exporting is False
        assert fb.is_export_running is False
        assert cancelled == [True]

    def test_cancel_noop_when_not_exporting(self):
        vm, _ = _build_vm()
        vm.cancel()
        assert vm.is_exporting is False


class TestColormapResolution:
    def test_returns_enum_for_valid_config_value(self):
        vm, _ = _build_vm()
        vm._config.set("gui:export:cluster_png_colormap", "plasma")
        assert vm.colormap is Colormap.PLASMA

    def test_falls_back_to_viridis_on_invalid_value(self, caplog):
        vm, _ = _build_vm()
        vm._config.set("gui:export:cluster_png_colormap", "not-a-map")
        with caplog.at_level("WARNING"):
            assert vm.colormap is Colormap.VIRIDIS
        assert any("cluster_png_colormap" in r.message for r in caplog.records)


class TestLabelsForwarding:
    def test_export_forwards_labels_into_request(self, tmp_path):
        """When the View passes labels, the request carries them verbatim."""
        vm, fb = _build_vm()
        fb.apply_time_preset("24h")

        captured: dict = {}

        def fake_run_async(request, token, **kwargs):
            captured["request"] = request
            # Simulate immediate completion so state resets.
            cb = kwargs.get("on_complete")
            if cb is not None:
                cb(request.out_path)

            class _Dummy:
                def join(self, timeout=None):
                    pass

                def is_alive(self):
                    return False

            return _Dummy()

        vm._service.run_async = fake_run_async
        labels = ClusterMetadataLabels.default_english()
        vm.export(tmp_path / "out.h5", ClusterQueryFilter(), labels=labels)
        assert captured["request"].labels is labels

    def test_export_defaults_labels_when_omitted(self, tmp_path):
        vm, fb = _build_vm()
        fb.apply_time_preset("24h")

        captured: dict = {}

        def fake_run_async(request, token, **kwargs):
            captured["labels"] = request.labels

            class _Dummy:
                def join(self, timeout=None):
                    pass

                def is_alive(self):
                    return False

            return _Dummy()

        vm._service.run_async = fake_run_async
        vm.export(tmp_path / "out.h5", ClusterQueryFilter())
        assert isinstance(captured["labels"], ClusterMetadataLabels)


class TestDefaultExportPath:
    def test_path_contains_today_date(self):
        vm, _ = _build_vm()
        today = datetime.now().strftime("%Y%m%d")
        assert f"mlccd-export-{today}" in vm.default_export_path

    def test_path_uses_config_directory(self, tmp_path):
        vm, _ = _build_vm()
        vm._config.set("gui:export:default_path", str(tmp_path))
        result = vm.default_export_path
        assert result.startswith(str(tmp_path))
        assert "mlccd-export-" in result

    def test_path_expands_tilde(self):
        vm, _ = _build_vm()
        vm._config.set("gui:export:default_path", "~")
        result = vm.default_export_path
        assert not result.startswith("~")


class TestIncludePngs:
    def _fake_run_async(self, captured):
        def fake_run_async(request, token, **kwargs):
            captured["request"] = request
            cb = kwargs.get("on_complete")
            if cb is not None:
                cb(request.out_path)

            class _Dummy:
                def join(self, timeout=None):
                    pass

                def is_alive(self):
                    return False

            return _Dummy()

        return fake_run_async

    def test_include_pngs_forwarded_to_request(self, tmp_path):
        vm, fb = _build_vm()
        fb.apply_time_preset("24h")
        captured: dict = {}
        vm._service.run_async = self._fake_run_async(captured)
        vm.export(tmp_path / "out.h5", ClusterQueryFilter(), include_pngs=True)
        assert captured["request"].include_pngs is True

    def test_include_pngs_defaults_to_false(self, tmp_path):
        vm, fb = _build_vm()
        fb.apply_time_preset("24h")
        captured: dict = {}
        vm._service.run_async = self._fake_run_async(captured)
        vm.export(tmp_path / "out.h5", ClusterQueryFilter())
        assert captured["request"].include_pngs is False


def _build_weighted_vm(
    *, fits: float = 0.70, h5: float = 0.10, png: float = 0.20
) -> HistoricalExportViewModel:
    cfg = MockConfigurationService()
    cfg.set("gui:export:progress_weight_fits", fits)
    cfg.set("gui:export:progress_weight_h5", h5)
    cfg.set("gui:export:progress_weight_png", png)
    physics = _FakePhysics()
    filter_bar = HistoricalFilterBarViewModel(cfg, physics)
    svc = HistoricalExportService(
        _NoopRepo(), _NoopStorage(), _NoopPNG(), physics, _NoopThumbnails()
    )
    return HistoricalExportViewModel(cfg, physics, svc, filter_bar)


class TestAggregatedFraction:
    def test_query_stage_returns_indeterminate(self) -> None:
        vm = _build_weighted_vm()
        assert vm.aggregated_fraction(0, 0, "query") == -1.0

    def test_zero_total_returns_indeterminate(self) -> None:
        vm = _build_weighted_vm()
        assert vm.aggregated_fraction(0, 0, "fits") == -1.0

    def test_fits_stage_covers_first_slice(self) -> None:
        vm = _build_weighted_vm(fits=0.7, h5=0.1, png=0.2)
        assert vm.aggregated_fraction(0, 100, "fits") == pytest.approx(0.0)
        assert vm.aggregated_fraction(50, 100, "fits") == pytest.approx(0.35)
        assert vm.aggregated_fraction(100, 100, "fits") == pytest.approx(0.70)

    def test_h5_stage_starts_where_fits_ends(self) -> None:
        vm = _build_weighted_vm(fits=0.7, h5=0.1, png=0.2)
        assert vm.aggregated_fraction(0, 100, "h5") == pytest.approx(0.70)
        assert vm.aggregated_fraction(100, 100, "h5") == pytest.approx(0.80)

    def test_png_stage_ends_at_one(self) -> None:
        vm = _build_weighted_vm(fits=0.7, h5=0.1, png=0.2)
        assert vm.aggregated_fraction(0, 100, "png") == pytest.approx(0.80)
        assert vm.aggregated_fraction(100, 100, "png") == pytest.approx(1.0)

    def test_weights_are_renormalised_when_they_do_not_sum_to_one(self) -> None:
        # Raw weights sum to 2.0; expect each slice halved.
        vm = _build_weighted_vm(fits=1.4, h5=0.2, png=0.4)
        assert vm.aggregated_fraction(100, 100, "fits") == pytest.approx(0.70)
        assert vm.aggregated_fraction(100, 100, "h5") == pytest.approx(0.80)
        assert vm.aggregated_fraction(100, 100, "png") == pytest.approx(1.0)

    def test_all_zero_weights_falls_back_to_defaults(self) -> None:
        vm = _build_weighted_vm(fits=0.0, h5=0.0, png=0.0)
        assert vm.aggregated_fraction(100, 100, "png") == pytest.approx(1.0)
        assert vm.aggregated_fraction(100, 100, "fits") == pytest.approx(0.70)

    def test_unknown_stage_returns_indeterminate(self) -> None:
        vm = _build_weighted_vm()
        assert vm.aggregated_fraction(1, 10, "bogus") == -1.0

    def test_fraction_never_exceeds_one(self) -> None:
        vm = _build_weighted_vm()
        # done > total should not overshoot (defensive clamp).
        assert vm.aggregated_fraction(150, 100, "png") == pytest.approx(1.0)
