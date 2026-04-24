# Validate query -> h5 -> png pipeline, cancel cleanup, error propagation

"""Tests for HistoricalExportService."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterExportService import (
    ClusterExportService,
    ClusterMetadataLabels,
)
from le_beta_vis.common.Colormap import Colormap
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.ExportStorageService import (
    CancelToken,
    ExportProvenance,
    ExportStorageService,
)
from le_beta_vis.common.HistoricalExportService import (
    ExportRequest,
    HistoricalExportService,
)
from le_beta_vis.common.PhysicsConversionManager import (
    PhysicsConversionManagerImpl,
)
from le_beta_vis.common.ThumbnailLoaderService import ThumbnailLoaderService

from mock_configuration_service import MockConfigurationService


def _physics() -> PhysicsConversionManagerImpl:
    cfg = MockConfigurationService()
    cfg.set("global:physics:kev_conversion", 1.0e-5)
    cfg.set("global:physics:ped_width", 1400)
    return PhysicsConversionManagerImpl(cfg)


class _FakeRepo(EventRepository):
    def __init__(self, clusters: List[Cluster], error: Optional[str] = None) -> None:
        self._clusters = clusters
        self._error = error

    def fetch_events(self, callback, on_error):
        callback(list(self._clusters))

    def query_clusters(self, query_filter, callback, on_error):
        if self._error is not None:
            on_error(self._error)
            return
        callback(list(self._clusters))

    def query_recent_clusters(self, limit, offset, callback, on_error):
        callback([])


class _FakeStorage(ExportStorageService):
    def __init__(self) -> None:
        self.written_clusters: List[Cluster] = []

    def write(self, out_path, clusters, provenance, cancel_token, on_progress=None):
        out_path.write_bytes(b"fake-h5")
        self.written_clusters = list(clusters)
        if on_progress is not None:
            for i, _ in enumerate(clusters):
                on_progress(i + 1, len(clusters))


class _FakePNG(ClusterExportService):
    def __init__(self) -> None:
        super().__init__()
        self.exported: List[Path] = []
        self.render_to_bytes_calls: List[int] = []
        self.seen_labels: Optional[ClusterMetadataLabels] = None

    def export(self, cluster, out_path, *, context, colormap):
        out_path.write_bytes(b"fake-png")
        self.exported.append(out_path)
        self.seen_labels = context.labels

    def render_to_bytes(self, cluster, *, context, colormap):
        self.render_to_bytes_calls.append(cluster.clusterId)
        self.seen_labels = context.labels
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    def render_metadata(self, canvas, metadata, labels):
        # Not exercised — export() is stubbed above.
        pass


class _FakeThumbnailService(ThumbnailLoaderService):
    """Synchronously fires on_ready with a fixed 2×2 float array."""

    def request_thumbnail(self, key, cluster, on_ready):
        pass

    def clear(self):
        pass

    def evict(self, keep_keys):
        pass

    def get_cached(self, key):
        return None

    def request_cluster_data(self, cluster, on_ready):
        on_ready(np.ones((2, 2), dtype=np.float64))

    def shutdown(self):
        pass


def _cluster(cid: int = 1) -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(0, 0, 2, 2),
        data=np.zeros((2, 2)),
        centerX=1,
        centerY=1,
        energy=100.0,
        pixelCount=4,
        clusterId=cid,
    )


def _provenance() -> ExportProvenance:
    return ExportProvenance(
        app_version="t",
        export_timestamp_utc="now",
        filter_json="{}",
        calibration_kev_conversion_factor=1.0e-5,
        calibration_pedestal_width=1400,
        hostname="h",
        user="u",
        machine_id="aa:bb:cc:dd:ee:ff",
    )


def _request(out: Path, labels: Optional[ClusterMetadataLabels] = None) -> ExportRequest:
    return ExportRequest(
        out_path=out,
        query_filter=None,
        provenance=_provenance(),
        colormap=Colormap.VIRIDIS,
        labels=labels or ClusterMetadataLabels.default_english(),
    )


def _run_and_wait(
    svc: HistoricalExportService,
    request: ExportRequest,
    token: CancelToken,
    *,
    on_progress=None,
    on_complete=None,
    on_error=None,
    on_cancelled=None,
) -> None:
    thread = svc.run_async(
        request, token,
        on_progress=on_progress,
        on_complete=on_complete,
        on_error=on_error,
        on_cancelled=on_cancelled,
    )
    thread.join(timeout=5.0)
    assert not thread.is_alive()


class TestHistoricalExportService:
    def test_happy_path_no_pngs_by_default(self, tmp_path: Path) -> None:
        out = tmp_path / "e.h5"
        clusters = [_cluster(1), _cluster(2)]
        png = _FakePNG()
        labels = ClusterMetadataLabels.default_english()
        svc = HistoricalExportService(
            _FakeRepo(clusters), _FakeStorage(), png, _physics(), _FakeThumbnailService()
        )
        completed: List[Path] = []

        _run_and_wait(
            svc,
            _request(out, labels=labels),
            CancelToken(),
            on_complete=completed.append,
        )

        assert out.exists()
        assert not (tmp_path / "e_images").exists()
        assert completed == [out]
        assert png.render_to_bytes_calls == []

    def test_happy_path_with_include_pngs(self, tmp_path: Path) -> None:
        import zipfile as zf_mod

        out = tmp_path / "e.zip"
        clusters = [_cluster(1), _cluster(2)]
        png = _FakePNG()
        labels = ClusterMetadataLabels.default_english()
        svc = HistoricalExportService(
            _FakeRepo(clusters), _FakeStorage(), png, _physics(), _FakeThumbnailService()
        )
        completed: List[Path] = []
        request = ExportRequest(
            out_path=out,
            query_filter=None,
            provenance=_provenance(),
            colormap=Colormap.VIRIDIS,
            labels=labels,
            include_pngs=True,
        )

        _run_and_wait(svc, request, CancelToken(), on_complete=completed.append)

        assert completed == [out]
        assert out.exists()
        assert not (tmp_path / "e.h5").exists()  # temp h5 cleaned up after zipping
        assert len(png.render_to_bytes_calls) == 2
        assert png.seen_labels is labels
        with zf_mod.ZipFile(out, "r") as z:
            names = z.namelist()
            assert "e.h5" in names
            assert "cluster_cards/1.png" in names
            assert "cluster_cards/2.png" in names

    def test_cancel_before_start_cleans_outputs(self, tmp_path: Path) -> None:
        out = tmp_path / "e.h5"
        token = CancelToken()
        token.cancel()
        svc = HistoricalExportService(
            _FakeRepo([_cluster(1)]), _FakeStorage(), _FakePNG(), _physics(), _FakeThumbnailService()
        )

        _run_and_wait(svc, _request(out), token)

        assert not out.exists()

    def test_cancel_before_start_calls_on_cancelled(self, tmp_path: Path) -> None:
        out = tmp_path / "e.h5"
        token = CancelToken()
        token.cancel()
        svc = HistoricalExportService(
            _FakeRepo([_cluster(1)]), _FakeStorage(), _FakePNG(), _physics(), _FakeThumbnailService()
        )
        cancelled: List[bool] = []
        errors: List[str] = []
        completions: List[Path] = []

        _run_and_wait(
            svc,
            _request(out),
            token,
            on_complete=completions.append,
            on_error=errors.append,
            on_cancelled=lambda: cancelled.append(True),
        )

        assert cancelled == [True]
        assert completions == []
        assert errors == []
        assert not out.exists()

    def test_repo_error_propagates_and_cleans_outputs(self, tmp_path: Path) -> None:
        out = tmp_path / "e.h5"
        errors: List[str] = []
        svc = HistoricalExportService(
            _FakeRepo([], error="db down"), _FakeStorage(), _FakePNG(), _physics(), _FakeThumbnailService()
        )

        _run_and_wait(
            svc,
            _request(out),
            CancelToken(),
            on_error=errors.append,
        )

        assert errors and "db down" in errors[0]
        assert not out.exists()

    def test_progress_callback_receives_h5_and_png_stages(self, tmp_path: Path) -> None:
        out = tmp_path / "e.h5"
        stages: List[str] = []
        svc = HistoricalExportService(
            _FakeRepo([_cluster(1), _cluster(2)]),
            _FakeStorage(),
            _FakePNG(),
            _physics(),
            _FakeThumbnailService(),
        )
        request = ExportRequest(
            out_path=out,
            query_filter=None,
            provenance=_provenance(),
            colormap=Colormap.VIRIDIS,
            labels=ClusterMetadataLabels.default_english(),
            include_pngs=True,
        )

        _run_and_wait(
            svc,
            request,
            CancelToken(),
            on_progress=lambda d, t, s: stages.append(s),
        )

        assert "query" in stages
        assert "fits" in stages
        assert "h5" in stages
        assert "png" in stages

    def test_post_query_zero_fits_progress_fires_before_hydration(
        self, tmp_path: Path
    ) -> None:
        out = tmp_path / "e.h5"
        events: List[tuple] = []
        svc = HistoricalExportService(
            _FakeRepo([_cluster(1), _cluster(2)]),
            _FakeStorage(),
            _FakePNG(),
            _physics(),
            _FakeThumbnailService(),
        )

        _run_and_wait(
            svc,
            _request(out),
            CancelToken(),
            on_progress=lambda d, t, s: events.append((d, t, s)),
        )

        fits_events = [(d, t) for d, t, s in events if s == "fits"]
        # First fits event must be (0, 2) — fired right after query completes
        assert fits_events[0] == (0, 2)
        # Subsequent events count up from 1
        assert fits_events[1] == (1, 2)
        assert fits_events[2] == (2, 2)

    def test_hydrate_pixel_data_populates_cluster_data(self, tmp_path: Path) -> None:
        out = tmp_path / "e.h5"
        storage = _FakeStorage()
        cluster = _cluster(1)
        cluster.data = None
        svc = HistoricalExportService(
            _FakeRepo([cluster]),
            storage,
            _FakePNG(),
            _physics(),
            _FakeThumbnailService(),
        )

        _run_and_wait(svc, _request(out), CancelToken())

        written = storage.written_clusters
        assert len(written) == 1
        assert written[0].data is not None
        assert written[0].data.shape == (2, 2)

    def test_hydrate_pixel_data_missing_data_does_not_crash(self, tmp_path: Path) -> None:
        """A cluster whose FITS data cannot be loaded should not abort the export."""

        class _NoDataThumbnails(_FakeThumbnailService):
            def request_cluster_data(self, cluster, on_ready):
                on_ready(None)

        out = tmp_path / "e.h5"
        storage = _FakeStorage()
        cluster = _cluster(1)
        cluster.data = None
        errors: List[str] = []
        completed: List[Path] = []
        svc = HistoricalExportService(
            _FakeRepo([cluster]),
            storage,
            _FakePNG(),
            _physics(),
            _NoDataThumbnails(),
        )

        _run_and_wait(svc, _request(out), CancelToken(), on_complete=completed.append, on_error=errors.append)

        assert not errors
        assert completed == [out]
        assert storage.written_clusters[0].data is None
