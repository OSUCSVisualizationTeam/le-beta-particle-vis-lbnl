"""Tests for RawDataAnnotationsViewModel.

Verifies handler injection, async refresh/apply, visibility filtering, hit-testing, and observer callback firing.

Pure Python tests — no QApplication instantiation.
"""

import threading
import time
from typing import List, Optional

import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.EPSDataClasses import ClusterQueryFilter
from le_beta_vis.common.EventRepository import fetch_all_hdu_clusters_sync
from le_beta_vis.frontend.viewmodels.RawDataAnnotationsViewModel import (
    RawDataAnnotationsViewModel,
)


def _cluster(
    top=0, left=0, bottom=10, right=10, cnn=0.0, nrg=0.0, bdt=0.0,
):
    return Cluster(
        boundingBox=BoundingBox(top, left, bottom, right),
        data=None,
        centerX=(left + right) // 2,
        centerY=(top + bottom) // 2,
        cnnClassification=cnn,
        nrgClassification=nrg,
        bdtClassification=bdt,
    )


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def vm():
    return RawDataAnnotationsViewModel(
        show_low_confidence_provider=lambda: True,
        threshold_provider=lambda: 0.5,
    )


class TestHandlerInjectionAndRefresh:
    def test_refresh_without_handlers_clears_and_no_ops(self, vm):
        vm.setFitsLookupHandler(None)
        vm.setClusterFetchHandler(None)
        vm.refresh("/tmp/some.fits", 0)
        assert vm.annotations == []

    def test_refresh_none_path_clears(self, vm):
        vm.refresh(None, 0)
        assert vm.annotations == []

    def test_refresh_fits_id_not_found_leaves_empty(self, vm):
        vm.setFitsLookupHandler(lambda path: None)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [_cluster()])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: vm.annotations == [])

    def test_refresh_populates_annotations(self, vm):
        clusters = [_cluster(cnn=0.9)]
        vm.setFitsLookupHandler(lambda path: 42)
        vm.setClusterFetchHandler(lambda fits_id, hdu: clusters)
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: vm.annotations == clusters)

    def test_refresh_passes_fits_id_and_hdu_to_fetch_handler(self, vm):
        seen = {}
        event = threading.Event()

        def fetch(fits_id, hdu_index):
            seen["fits_id"] = fits_id
            seen["hdu_index"] = hdu_index
            event.set()
            return []

        vm.setFitsLookupHandler(lambda path: 7)
        vm.setClusterFetchHandler(fetch)
        vm.refresh("/tmp/some.fits", 3)
        assert event.wait(timeout=2.0)
        assert seen == {"fits_id": 7, "hdu_index": 3}

    def test_fetch_handler_exception_leaves_empty(self, vm):
        def raise_error(fits_id, hdu):
            raise RuntimeError("boom")

        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(raise_error)
        vm.refresh("/tmp/some.fits", 0)
        time.sleep(0.1)
        assert vm.annotations == []

    def test_stale_refresh_is_discarded(self, vm):
        """A slower first fetch must not overwrite a faster later one."""
        release_first = threading.Event()

        def slow_fetch(fits_id, hdu):
            release_first.wait(timeout=2.0)
            return [_cluster(cnn=0.1)]

        def fast_fetch(fits_id, hdu):
            return [_cluster(cnn=0.9)]

        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(slow_fetch)
        vm.refresh("/tmp/first.fits", 0)

        vm.setClusterFetchHandler(fast_fetch)
        vm.refresh("/tmp/second.fits", 0)
        assert _wait_until(
            lambda: len(vm.annotations) == 1
            and vm.annotations[0].cnnClassification == 0.9
        )

        release_first.set()
        time.sleep(0.1)
        assert vm.annotations[0].cnnClassification == 0.9


class TestClear:
    def test_clear_empties_annotations(self, vm):
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [_cluster()])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        vm.clear()
        assert vm.annotations == []


class TestVisibleAnnotationsFilter:
    def test_shows_all_when_low_confidence_visible(self):
        vm = RawDataAnnotationsViewModel(
            show_low_confidence_provider=lambda: True,
            threshold_provider=lambda: 0.5,
        )
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(
            lambda fits_id, hdu: [_cluster(cnn=0.1), _cluster(cnn=0.9)]
        )
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 2)
        assert len(vm.visibleAnnotations) == 2

    def test_hides_below_threshold_when_disabled(self):
        vm = RawDataAnnotationsViewModel(
            show_low_confidence_provider=lambda: False,
            threshold_provider=lambda: 0.5,
        )
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(
            lambda fits_id, hdu: [_cluster(cnn=0.1), _cluster(cnn=0.9)]
        )
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 2)
        visible = vm.visibleAnnotations
        assert len(visible) == 1
        assert visible[0].cnnClassification == 0.9

    def test_threshold_boundary_is_inclusive(self):
        vm = RawDataAnnotationsViewModel(
            show_low_confidence_provider=lambda: False,
            threshold_provider=lambda: 0.5,
        )
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(
            lambda fits_id, hdu: [_cluster(nrg=0.5)]
        )
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        assert len(vm.visibleAnnotations) == 1


class TestHitTest:
    def test_hit_inside_bbox(self, vm):
        c = _cluster(top=5, left=5, bottom=15, right=15)
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [c])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        assert vm.hitTest(10, 10) is c

    def test_miss_outside_bbox(self, vm):
        c = _cluster(top=5, left=5, bottom=15, right=15)
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [c])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        assert vm.hitTest(0, 0) is None

    def test_half_open_bounds(self, vm):
        c = _cluster(top=5, left=5, bottom=15, right=15)
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [c])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        assert vm.hitTest(5, 5) is c
        assert vm.hitTest(15, 15) is None
        assert vm.hitTest(14, 14) is c

    def test_hit_with_inverted_top_bottom(self, vm):
        """EPS-sourced clusters store top/bottom with the row axis flipped relative to locally-extracted ones (top > bottom).

        hitTest must normalize the span rather than assume ordering.
        """
        c = _cluster(top=15, left=5, bottom=5, right=15)
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [c])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        assert vm.hitTest(10, 10) is c
        assert vm.hitTest(0, 0) is None

    def test_hit_test_respects_visibility_filter(self):
        vm = RawDataAnnotationsViewModel(
            show_low_confidence_provider=lambda: False,
            threshold_provider=lambda: 0.5,
        )
        low_confidence = _cluster(top=0, left=0, bottom=10, right=10, cnn=0.1)
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [low_confidence])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(vm.annotations) == 1)
        assert vm.hitTest(5, 5) is None


class _FakePagedEventRepository:
    """Duck-typed fake ``EventRepository`` backed by a fixed cluster list, used to prove the annotation fetch path
    (fetch_all_hdu_clusters_sync wired into a RawDataAnnotationsViewModel handler, mirroring
    RawDataView._onAnnotationClusterFetch) doesn't silently truncate to a single page (issue #241)."""

    def __init__(self, clusters: List[Cluster]):
        self._clusters = clusters

    def fetch_clusters_sync(
        self,
        limit: Optional[int],
        offset: int,
        query_filter: Optional[ClusterQueryFilter] = None,
    ) -> List[Cluster]:
        return self._clusters[offset:offset + limit]


class TestPagedAnnotationFetch:
    def test_hdu_with_more_clusters_than_a_single_page_is_not_truncated(self, vm):
        """Regression test for issue #241: a HDU holding more clusters than eps:retrieval_limit_default must still show up in
        full, not just its first page."""
        page_limit = 500
        total_clusters = 1200
        clusters = [_cluster(top=i, bottom=i + 10) for i in range(total_clusters)]
        repo = _FakePagedEventRepository(clusters)

        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(
            lambda fits_id, hdu: fetch_all_hdu_clusters_sync(
                repo, fits_id=fits_id, hdu_id=hdu, page_limit=page_limit
            )
        )
        vm.refresh("/tmp/some.fits", 0)

        assert _wait_until(lambda: len(vm.annotations) == total_clusters)


class TestObserverCallback:
    def test_callback_fires_on_refresh_completion(self, vm):
        calls = []
        vm.add_annotations_changed_callback(lambda: calls.append(True))
        vm.setFitsLookupHandler(lambda path: 1)
        vm.setClusterFetchHandler(lambda fits_id, hdu: [_cluster()])
        vm.refresh("/tmp/some.fits", 0)
        assert _wait_until(lambda: len(calls) >= 2)

    def test_callback_fires_on_clear(self, vm):
        calls = []
        vm.add_annotations_changed_callback(lambda: calls.append(True))
        vm.clear()
        assert len(calls) == 1
