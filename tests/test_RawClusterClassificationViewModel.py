"""Unit tests for RawClusterClassificationViewModel (issue #153)."""
import threading
from typing import List, Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.ClassifierDataClasses import ClassificationRequestCluster
from le_beta_vis.common.ClassifierService import (
    ClassificationBatchResult,
    ClassificationResult,
    ClassificationScore,
    ClassifierService,
    ClusterScores,
    CompletionCallback,
    ErrorCallback,
)
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.frontend.viewmodels.RawClusterClassificationViewModel import (
    Phase,
    RawClusterClassificationViewModel,
    _confidence_at,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cluster(energy: float = 1000.0) -> ClusteredEventInfo:
    bb = BoundingBox(top=0, left=0, bottom=4, right=4)
    cluster = ClusteredEventInfo.__new__(ClusteredEventInfo)
    cluster.boundingBox = bb
    cluster.data = np.ones((4, 4), dtype=np.float32) * energy
    cluster.centerX = 2
    cluster.centerY = 2
    cluster.sigmaX = 1.0
    cluster.sigmaY = 1.0
    cluster.energy = energy
    cluster.pixelCount = 16
    return cluster


def _make_batch(
    n: int,
    model: str,
    confidence: Optional[float] = 0.9,
) -> ClassificationBatchResult:
    results = [
        ClassificationResult(
            cluster_id=i,
            model=model,
            score=ClassificationScore(
                particle_type=MagicMock(), confidence=confidence
            )
            if confidence is not None
            else None,
        )
        for i in range(n)
    ]
    failed = sum(1 for r in results if r.score is None)
    return ClassificationBatchResult(results=results, total=n, failed=failed)


class _SyncClassifierService(ClassifierService):
    """Minimal synchronous mock used by tests."""

    def __init__(
        self,
        cnn_conf: Optional[float] = 0.8,
        nrg_conf: Optional[float] = 0.6,
        bdt_conf: Optional[float] = 0.7,
    ) -> None:
        self._cnn_conf = cnn_conf
        self._nrg_conf = nrg_conf
        self._bdt_conf = bdt_conf

    def _call(
        self,
        n: int,
        model: str,
        confidence: Optional[float],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback],
    ) -> None:
        on_complete(_make_batch(n, model, confidence))

    def classify_cnn(self, clusters, on_complete, on_error=None):
        self._call(len(clusters), "CNN", self._cnn_conf, on_complete, on_error)

    def classify_nrg(self, clusters, on_complete, on_error=None):
        self._call(len(clusters), "NRG", self._nrg_conf, on_complete, on_error)

    def classify_bdt(self, clusters, on_complete, on_error=None):
        self._call(len(clusters), "BDT", self._bdt_conf, on_complete, on_error)


def _build_vm(
    clusters: Optional[List[ClusteredEventInfo]] = None,
    service: Optional[ClassifierService] = None,
) -> RawClusterClassificationViewModel:
    if clusters is None:
        clusters = [_make_cluster(), _make_cluster(500.0)]
    if service is None:
        service = _SyncClassifierService()
    physics = MagicMock()
    physics.adu_to_kev.side_effect = lambda e: float(e) * 1e-5
    return RawClusterClassificationViewModel(
        clusters=clusters, service=service, physics=physics
    )


def _run_and_wait(vm: RawClusterClassificationViewModel) -> None:
    """Calls classify() and blocks until POST phase is reached."""
    done = threading.Event()
    phases: List[Phase] = []

    def on_phase():
        phases.append(vm.phase)
        if vm.phase == Phase.POST:
            done.set()

    vm.add_phase_changed_callback(on_phase)
    vm.classify()
    done.wait(timeout=5.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_initial_phase_is_pre():
    vm = _build_vm()
    assert vm.phase == Phase.PRE


def test_initial_scores_empty():
    vm = _build_vm()
    assert vm.scores == {}


def test_classify_transitions_to_in_flight_then_post():
    vm = _build_vm()
    seen: List[Phase] = []
    done = threading.Event()

    def on_phase():
        seen.append(vm.phase)
        if vm.phase == Phase.POST:
            done.set()

    vm.add_phase_changed_callback(on_phase)
    vm.classify()
    done.wait(timeout=5.0)

    assert Phase.IN_FLIGHT in seen
    assert Phase.POST in seen
    assert seen[-1] == Phase.POST


def test_scores_populated_after_classification():
    clusters = [_make_cluster(), _make_cluster(200.0), _make_cluster(300.0)]
    vm = _build_vm(clusters=clusters)
    _run_and_wait(vm)

    assert len(vm.scores) == 3
    for i in range(3):
        assert i in vm.scores
        s = vm.scores[i]
        assert isinstance(s, ClusterScores)
        assert s.cnn == pytest.approx(0.8)
        assert s.nrg == pytest.approx(0.6)
        assert s.bdt == pytest.approx(0.7)


def test_failed_model_produces_none_confidence():
    service = _SyncClassifierService(cnn_conf=None, nrg_conf=0.5, bdt_conf=0.4)
    vm = _build_vm(service=service)
    _run_and_wait(vm)

    assert vm.scores[0].cnn is None
    assert vm.scores[0].nrg == pytest.approx(0.5)
    assert vm.scores[0].bdt == pytest.approx(0.4)


def test_classify_from_post_is_noop():
    vm = _build_vm()
    _run_and_wait(vm)
    assert vm.phase == Phase.POST

    callback_count = []
    vm.add_phase_changed_callback(lambda: callback_count.append(1))
    vm.classify()
    # No new background thread should have fired any callback
    assert callback_count == []
    assert vm.phase == Phase.POST


def test_energy_kev_delegates_to_physics():
    clusters = [_make_cluster(1000.0)]
    vm = _build_vm(clusters=clusters)
    assert vm.energy_kev(0) == pytest.approx(1000.0 * 1e-5)


def test_to_request_clusters_uses_index_as_cluster_id():
    clusters = [_make_cluster(), _make_cluster()]
    vm = _build_vm(clusters=clusters)
    request = vm._to_request_clusters()
    assert request[0].cluster_id == 0
    assert request[1].cluster_id == 1


def test_confidence_at_returns_none_for_empty_batch():
    assert _confidence_at(None, 0) is None


def test_confidence_at_returns_none_for_failed_result():
    batch = _make_batch(1, "CNN", confidence=None)
    assert _confidence_at(batch, 0) is None


def test_confidence_at_returns_confidence_for_valid_result():
    batch = _make_batch(1, "CNN", confidence=0.85)
    assert _confidence_at(batch, 0) == pytest.approx(0.85)


def test_phase_changed_callback_remove():
    vm = _build_vm()
    calls = []
    def cb(): return calls.append(1)
    vm.add_phase_changed_callback(cb)
    vm.remove_phase_changed_callback(cb)

    done = threading.Event()
    vm.add_phase_changed_callback(lambda: done.set() if vm.phase == Phase.POST else None)
    vm.classify()
    done.wait(timeout=5.0)

    assert calls == []
