"""Live/manual-verification tests for the full ViewModel -> EPS -> MySQL round trip (issue #205).

Everything else in this codebase mocks either the ZMQ layer (``test_ZMQBasedEventRepository.py``) or the MySQL connection
(``test_EventPersistenceService.py``). These tests instead drive real ViewModels against a real ``ZMQBasedEventRepository``,
talking over real ZMQ sockets to a real ``EventPersistence`` instance (started in-thread by the ``live_eps`` fixture -- see
``tests/live_eps_fixture.py``) backed by a real MySQL database. Assertions are made against seeded database state, never
against a mocked return value.

Skipped by default; set ``LBNLVIS_LIVE_TESTS=1`` to run, with a MySQL server carrying the ``lbnlfits`` schema reachable at
``localhost`` (see ``database-docker/docker-compose.yml`` for a local one, or the CI-provisioned one in
``.github/workflows/regression-integration.yml``):

LBNLVIS_LIVE_TESTS=1 PYTHONPATH=src uv run pytest tests/test_live_eps_mysql_roundtrip.py -v

Follows the ``tests/test_live_startup_readiness.py`` convention (see that file's docstring).
"""

import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from live_eps_fixture import live_eps, raw_connection, unique_marker  # noqa: F401
from MockThumbnailLoaderService import MockThumbnailLoaderService

from le_beta_vis.backend.FileProcessing import process_file
from le_beta_vis.backend.InMemoryClusterStorageBuffer import (
    InMemoryClusterStorageBuffer,
)
from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    FitsQueryFilter,
)
from le_beta_vis.common.MockClassifierService import MockClassifierService
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManagerImpl
from le_beta_vis.frontend.viewmodels.HistoricalFilterBarViewModel import (
    HistoricalFilterBarViewModel,
)
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import HistoricalViewModel

pytestmark = pytest.mark.skipif(
    os.environ.get("LBNLVIS_LIVE_TESTS") != "1",
    reason="Live/manual-verification test; set LBNLVIS_LIVE_TESTS=1 to run.",
)

_WAIT_TIMEOUT_S = 5.0


def _insert_fits(cursor, filename: str, date: datetime) -> int:
    cursor.execute(
        "INSERT INTO fits_files (fileName, date, min, max, exposureTime) "
        "VALUES (%s, %s, %s, %s, %s)",
        (filename, date, 0.0, 1.0, 1.0),
    )
    return cursor.lastrowid


def _insert_cluster(cursor, fits_id: int, classification: str) -> int:
    cursor.execute(
        "INSERT INTO clusters "
        "(fitsFile, hdu_id, box_top, box_left, box_bottom, box_right, "
        " totalEnergy, sigmaX, sigmaY, classification, pixelCount) "
        "VALUES (%s, 0, 1, 2, 3, 4, 100.0, 1.0, 1.0, %s, 10)",
        (fits_id, classification),
    )
    return cursor.lastrowid


def _delete_fits_and_clusters(fits_ids) -> None:
    if not fits_ids:
        return
    conn = raw_connection()
    try:
        cursor = conn.cursor()
        placeholder = ", ".join(["%s"] * len(fits_ids))
        cursor.execute(
            f"DELETE FROM clusters WHERE fitsFile IN ({placeholder})", tuple(fits_ids)
        )
        cursor.execute(
            f"DELETE FROM fits_files WHERE fitsID IN ({placeholder})", tuple(fits_ids)
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def test_filtered_historical_query_returns_seeded_match(live_eps):  # noqa: F811
    """Historical filter bar -> HistoricalViewModel -> real EPS -> real MySQL.

    Seeds two fits_files rows (one inside the filter window, one 40 days outside it as a negative control) and three clusters
    split across matching/non-matching date and classification, then drives the real filter-bar and historical ViewModels and
    asserts only the one row that matches *both* criteria comes back.
    """
    marker = unique_marker("hist_filter")
    now = datetime.now().replace(microsecond=0)
    date_in_window = now - timedelta(hours=1)
    date_outside_window = now - timedelta(days=40)
    window_start = now - timedelta(hours=2)
    window_end = now

    fits_ids = []
    try:
        conn = raw_connection()
        cursor = conn.cursor()
        fits_a = _insert_fits(cursor, f"{marker}_a.fits", date_in_window)
        fits_b = _insert_fits(cursor, f"{marker}_b.fits", date_outside_window)
        conn.commit()
        fits_ids = [fits_a, fits_b]

        # Production ingest persists uppercase classification strings
        # (ParticleType.name, e.g. "TRITIUM") -- confirmed against the real
        # local lbnlfits database. Seed realistically.
        match_id = _insert_cluster(cursor, fits_a, "TRITIUM")
        _insert_cluster(cursor, fits_a, "MUON")  # right date, wrong classification
        _insert_cluster(cursor, fits_b, "TRITIUM")  # right classification, wrong date
        conn.commit()
        cursor.close()
        conn.close()

        physics = PhysicsConversionManagerImpl(live_eps.config)
        filter_bar = HistoricalFilterBarViewModel(live_eps.config, physics)
        filter_bar.start_datetime = window_start
        filter_bar.end_datetime = window_end
        # Lowercase, matching what the real UI actually sends
        # (classification_options lowercases ParticleType.name). The
        # clusters.classification column uses MySQL's default
        # case-insensitive collation (utf8mb4_0900_ai_ci), so this
        # correctly matches the uppercase-stored row seeded above.
        filter_bar.classification = "tritium"
        query_filter = filter_bar.build_filter()

        vm = HistoricalViewModel(
            live_eps.config, physics, live_eps.repository, MockThumbnailLoaderService()
        )
        vm.setQueryFilter(query_filter)

        done = threading.Event()
        errors = []
        vm.add_events_changed_callback(done.set)
        vm.add_load_error_callback(lambda err: (errors.append(err), done.set()))
        vm.loadEvents()

        assert done.wait(timeout=_WAIT_TIMEOUT_S), "historical query did not complete in time"
        assert not errors, f"historical query reported an error: {errors}"
        assert len(vm.events) == 1
        assert vm.events[0].clusterId == match_id
        # Returned as stored (uppercase) -- the lowercase filter value only
        # affects the WHERE-clause match, not the value MySQL returns.
        assert vm.events[0].classification == "TRITIUM"
    finally:
        _delete_fits_and_clusters(fits_ids)


def _make_synthetic_fits(tmp_path: Path) -> Path:
    """Builds a 4-HDU FITS file with exactly one extractable cluster.

    FileProcessing.store_fits unconditionally indexes capture[0..3], so at
    least 4 HDUs are required. Header keys DATESTART/DATEEND/DATE are
    required by CCDCaptureModel.Info.fromHDU (see
    tests/test_CCDCaptureModel.py::_make_temp_fits, the existing pattern
    this mirrors). HDU 0 carries a 3x3 block of value 50 centered at
    (10, 10) on an otherwise-zero 20x20 background; HDUs 1-3 are all-zero
    so exactly one cluster is produced across the whole file.
    """
    hdus = []
    shape = (20, 20)
    for idx in range(4):
        data = np.zeros(shape, dtype=np.float64)
        if idx == 0:
            data[9:12, 9:12] = 50.0
        hdu = fits.PrimaryHDU(data) if idx == 0 else fits.ImageHDU(data)
        hdu.header["DATESTART"] = "2025-01-01T00:00:00"
        hdu.header["DATEEND"] = "2025-01-01T00:01:00"
        hdu.header["DATE"] = "2025-01-01T00:00:30"
        hdus.append(hdu)
    hdul = fits.HDUList(hdus)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".fits", dir=tmp_path, delete=False
    )
    tmp_name = tmp.name
    tmp.close()
    hdul.writeto(tmp_name, overwrite=True)
    return Path(tmp_name)


def test_cluster_ingest_round_trip(live_eps, tmp_path):  # noqa: F811
    """FileProcessing.process_file() -> real EPS -> real MySQL -> query back.

    Ingests a synthetic FITS file through the real ingest pipeline (the same entry point InitializePolling.py calls in
    production) and confirms the resulting cluster is retrievable via EPS, not just present in the process's own in-memory
    buffer.
    """
    fits_path = _make_synthetic_fits(tmp_path)

    # Scoped to this test only (not baked into the shared fixture): makes
    # cluster-extraction thresholds trivial to reason about. Threshold
    # becomes `data > 4`; energy gate becomes `sum(cluster) >= 1`.
    live_eps.config.set("global:physics:ped_width", 1.0)
    live_eps.config.set("global:physics:kev_conversion", 1.0)

    fits_id = None
    try:
        process_file(
            config_service=live_eps.config,
            file=str(fits_path),
            cluster_storage_buffer_factory=InMemoryClusterStorageBuffer,
            classifier_service=MockClassifierService(),
        )

        fits_records = live_eps.repository.query_fits_sync(
            FitsQueryFilter(filename=str(fits_path))
        )
        assert len(fits_records) == 1
        fits_id = fits_records[0].fits_id

        clusters = live_eps.repository.query_clusters_sync(
            ClusterQueryFilter(fits_id=fits_id)
        )
        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster.hdu_id == 0
        assert cluster.pixelCount == 9
        assert cluster.energy == pytest.approx(450.0)
        # MockClassifierService draws unseeded randomness per cluster per
        # model (plus a simulated ~5% per-call failure branch), so only
        # membership -- not an exact value -- is safe to assert.
        assert cluster.classification in {"TRITIUM", "UNCLASSIFIED"}
    finally:
        if fits_id is not None:
            _delete_fits_and_clusters([fits_id])


def test_classification_update_persists_through_repository(live_eps):  # noqa: F811
    """ZMQBasedEventRepository.update_classification_sync() -> real EPS -> real MySQL.

    No production ViewModel calls update_classification today (see RawClusterLabelingViewModel.py's comment on why it
    deliberately doesn't), so this drives the repository directly -- matching the issue's own "through the repository" wording.
    """
    marker = unique_marker("classify_update")
    fits_ids = []
    try:
        conn = raw_connection()
        cursor = conn.cursor()
        fits_id = _insert_fits(cursor, f"{marker}.fits", datetime.now().replace(microsecond=0))
        conn.commit()
        fits_ids = [fits_id]
        cluster_id = _insert_cluster(cursor, fits_id, "UNCLASSIFIED")
        conn.commit()
        cursor.close()
        conn.close()

        updated = live_eps.repository.update_classification_sync(
            ClassificationUpdateRequest(cluster_id=cluster_id, classification="tritium")
        )
        assert updated is True

        results = live_eps.repository.query_clusters_sync(
            ClusterQueryFilter(cluster_id=cluster_id)
        )
        assert len(results) == 1
        assert results[0].classification == "tritium"

        # Defense-in-depth: confirm the value is truly persisted in MySQL,
        # not merely reflected back by some hypothetical repository cache.
        verify_conn = raw_connection()
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute(
            "SELECT classification FROM clusters WHERE clusterID = %s", (cluster_id,)
        )
        row = verify_cursor.fetchone()
        verify_cursor.close()
        verify_conn.close()
        assert row is not None
        assert row[0] == "tritium"
    finally:
        _delete_fits_and_clusters(fits_ids)
