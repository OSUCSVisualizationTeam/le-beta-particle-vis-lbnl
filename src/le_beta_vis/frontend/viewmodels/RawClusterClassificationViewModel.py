"""ViewModel for the ML cluster classification dialog (issue #153).

Scientists select clusters from a raw FITS frame and run the CNN, NRG, and BDT
models to obtain per-cluster particle-type confidence scores. Results propagate
back to ClusteredEventWidget via ClusterAnalysisViewModel.
"""

from __future__ import annotations

import logging
import threading
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from le_beta_vis.common.ClassifierDataClasses import ClassificationRequestCluster
from le_beta_vis.common.ClassifierService import (
    ClassificationBatchResult,
    ClassifierService,
    ClusterScores,
)
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager

logger = logging.getLogger(__name__)


class Phase(Enum):
    PRE = auto()
    IN_FLIGHT = auto()
    POST = auto()


class RawClusterClassificationViewModel:
    """Manages async ML classification for selected raw-data clusters.

    Pure Python — no Qt imports, no QObject inheritance. The dialog binds
    via add_phase_changed_callback and observes phase transitions to switch
    between form / spinner / results pages.
    """

    def __init__(
        self,
        clusters: List[ClusteredEventInfo],
        service: ClassifierService,
        physics: PhysicsConversionManager,
    ) -> None:
        self._clusters = clusters
        self._service = service
        self._physics = physics
        self._phase: Phase = Phase.PRE
        self._scores: Dict[int, ClusterScores] = {}
        self._error_message: Optional[str] = None
        self._phase_changed_callbacks: List[Callable[[], None]] = []

    # ------------------------------------------------------------------ state

    @property
    def clusters(self) -> List[ClusteredEventInfo]:
        """The clusters offered for classification."""
        return self._clusters

    @property
    def phase(self) -> Phase:
        """Current classification phase."""
        return self._phase

    @property
    def scores(self) -> Dict[int, ClusterScores]:
        """Per-cluster scores keyed by cluster list index. Empty until POST."""
        return dict(self._scores)

    @property
    def error_message(self) -> Optional[str]:
        """Set when a model call fails; None otherwise."""
        return self._error_message

    def energy_kev(self, index: int) -> float:
        """Returns cluster energy converted to keV."""
        return float(self._physics.adu_to_kev(self._clusters[index].energy))

    # --------------------------------------------------------------- callbacks

    def add_phase_changed_callback(self, cb: Callable[[], None]) -> None:
        """Registers cb to be called whenever the classification phase changes."""
        self._phase_changed_callbacks.append(cb)

    def remove_phase_changed_callback(self, cb: Callable[[], None]) -> None:
        """Unregisters cb."""
        try:
            self._phase_changed_callbacks.remove(cb)
        except ValueError:
            pass

    def _notify_phase_changed(self) -> None:
        for cb in list(self._phase_changed_callbacks):
            cb()

    # ------------------------------------------------------------------ action

    def classify(self) -> None:
        """Starts async classification for all clusters.

        Transitions PRE → IN_FLIGHT on the calling thread, then POST on the
        background thread after all three models finish. Calling from any
        phase other than PRE is a no-op.
        """
        if self._phase != Phase.PRE:
            return
        self._phase = Phase.IN_FLIGHT
        self._error_message = None
        self._notify_phase_changed()
        threading.Thread(target=self._run_classification, daemon=True).start()

    def _run_classification(self) -> None:
        request_clusters = self._to_request_clusters()

        def _call_model(
            classify_fn: Callable,
        ) -> Optional[ClassificationBatchResult]:
            result: Optional[ClassificationBatchResult] = None
            latch = threading.Event()

            def on_complete(batch: ClassificationBatchResult) -> None:
                nonlocal result
                result = batch
                latch.set()

            def on_error(exc: Exception) -> None:
                logger.error("Classifier model error: %s", exc)
                latch.set()

            # TODO(#XXX): MockClassifierService.classify_* fires on_complete
            # synchronously on this thread. Safe here because we are already in
            # a daemon Thread. ZMQBasedClassifierServer fires on_complete from
            # the ZMQ receive thread; the threading.Event latch handles both
            # cases correctly.
            classify_fn(request_clusters, on_complete, on_error)
            latch.wait()
            return result

        try:
            cnn_batch = _call_model(self._service.classify_cnn)
            nrg_batch = _call_model(self._service.classify_nrg)
            bdt_batch = _call_model(self._service.classify_bdt)
        except Exception as exc:
            logger.exception("Unexpected error during classification: %s", exc)
            self._error_message = str(exc)
            cnn_batch = nrg_batch = bdt_batch = None

        self._scores = self._build_scores(cnn_batch, nrg_batch, bdt_batch)
        self._phase = Phase.POST
        self._notify_phase_changed()

    def _build_scores(
        self,
        cnn_batch: Optional[ClassificationBatchResult],
        nrg_batch: Optional[ClassificationBatchResult],
        bdt_batch: Optional[ClassificationBatchResult],
    ) -> Dict[int, ClusterScores]:
        scores: Dict[int, ClusterScores] = {}
        for i in range(len(self._clusters)):
            scores[i] = ClusterScores(
                cnn=_confidence_at(cnn_batch, i),
                nrg=_confidence_at(nrg_batch, i),
                bdt=_confidence_at(bdt_batch, i),
            )
        return scores

    def _to_request_clusters(self) -> List[ClassificationRequestCluster]:
        # TODO(#XXX): cluster_id is the list index because ClusteredEventInfo
        # has no persistent ID. Safe because ClassificationBatchResult.results
        # is ordered to match the input list.
        result = []
        for i, cluster in enumerate(self._clusters):
            result.append(
                ClassificationRequestCluster(
                    data=cluster.data.tolist(),
                    cluster_id=i,
                    sigmaX=float(cluster.sigmaX),
                    sigmaY=float(cluster.sigmaY),
                    total_energy=float(cluster.energy),
                    total_pixels=int(cluster.pixelCount),
                )
            )
        return result


def _confidence_at(
    batch: Optional[ClassificationBatchResult], index: int
) -> Optional[float]:
    """Extracts confidence for the cluster at *index* from a batch, or None."""
    if batch is None or index >= len(batch.results):
        return None
    score = batch.results[index].score
    return score.confidence if score is not None else None
