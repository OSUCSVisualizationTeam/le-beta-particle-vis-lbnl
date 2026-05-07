"""ViewModel for the raw-data cluster labeling dialog (issue #195).

Scientists select clusters from a live FITS frame, assign a ground-truth
particle type label to each one, and submit them to EPS via store_cluster.
The stored records are later harvested for CNN/NRG/BDT retraining.
"""

from le_beta_vis.common.PhysicsConversionManager import PhysicsConversionManager
from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.common.EventRepository import EventRepository
from le_beta_vis.common.EPSDataClasses import ClusterStoreRequest
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.BoundingBox import BoundingBox
import logging
import threading
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Phase(Enum):
    IDLE = auto()
    SUBMITTING = auto()
    DONE = auto()
    ERROR = auto()


class RawClusterLabelingViewModel:
    """Manages per-cluster label state and async submission to EPS.

    Pure Python — no Qt imports, no QObject inheritance.  The dialog
    binds to this VM via add_phase_changed_callback and observes phase
    transitions to switch between form / spinner / result pages.
    """

    def __init__(
        self,
        clusters: List[ClusteredEventInfo],
        repository: EventRepository,
        physics: PhysicsConversionManager,
        fits_info_provider: Callable[[], Tuple[int, int]],
    ) -> None:
        self._clusters = clusters
        self._repository = repository
        self._physics = physics
        self._fits_info_provider = fits_info_provider
        self._labels: Dict[int, ParticleType] = {}
        self._phase: Phase = Phase.IDLE
        self._stored_count: int = 0
        self._error_message: Optional[str] = None
        self._phase_changed_callbacks: List[Callable[[], None]] = []

    # ------------------------------------------------------------------ state

    @property
    def clusters(self) -> List[ClusteredEventInfo]:
        """The clusters offered for labeling."""
        return self._clusters

    @property
    def phase(self) -> Phase:
        """Current submission phase."""
        return self._phase

    @property
    def stored_count(self) -> int:
        """Number of clusters successfully persisted on last submission."""
        return self._stored_count

    @property
    def error_message(self) -> Optional[str]:
        """Set when phase is ERROR; None otherwise."""
        return self._error_message

    # ----------------------------------------------------------------- labels

    def label_for(self, index: int) -> ParticleType:
        """Returns the current label for cluster *index*, defaulting to UNCLASSIFIED."""
        return self._labels.get(index, ParticleType.UNCLASSIFIED)

    def energy_kev(self, index: int) -> float:
        """Returns cluster energy converted to keV."""
        return float(self._physics.adu_to_kev(self._clusters[index].energy))

    def set_label(self, index: int, particle_type: ParticleType) -> None:
        """Sets the particle type label for a single cluster row."""
        self._labels[index] = particle_type

    def set_all_labels(self, particle_type: ParticleType) -> None:
        """Sets the same particle type label for every cluster."""
        for i in range(len(self._clusters)):
            self._labels[i] = particle_type

    # --------------------------------------------------------------- callbacks

    def add_phase_changed_callback(self, cb: Callable[[], None]) -> None:
        """Registers *cb* to be called whenever the submission phase changes."""
        self._phase_changed_callbacks.append(cb)

    def remove_phase_changed_callback(self, cb: Callable[[], None]) -> None:
        """Unregisters *cb*."""
        try:
            self._phase_changed_callbacks.remove(cb)
        except ValueError:
            pass

    def _notify_phase_changed(self) -> None:
        for cb in list(self._phase_changed_callbacks):
            cb()

    # ------------------------------------------------------------------ action

    def submit(self) -> None:
        """Submits all labeled (non-UNCLASSIFIED) clusters to EPS asynchronously.

        Transitions: IDLE → SUBMITTING (on this thread) then DONE or ERROR
        (on the background thread via _notify_phase_changed).
        """
        self._phase = Phase.SUBMITTING
        self._stored_count = 0
        self._error_message = None
        self._notify_phase_changed()
        threading.Thread(target=self._run_submission, daemon=True).start()

    def _run_submission(self) -> None:
        logger.info("Starting submission of %d cluster(s)", len(self._clusters))
        try:
            fits_id, hdu_id = self._fits_info_provider()
            count = 0
            for i, cluster in enumerate(self._clusters):
                if self.label_for(i) == ParticleType.UNCLASSIFIED:
                    continue
                request = self._build_request(cluster, hdu_id, fits_id, self.label_for(i))
                # store_cluster creates a new EPS record with the classification
                # already set in one round-trip. update_classification is
                # intentionally NOT called here — it requires a cluster_id and
                # is for retroactively relabeling clusters that were previously
                # stored without a label (e.g. from the Historical view).
                # ClusteredEventInfo objects have no cluster_id; they are
                # in-memory extraction results that have never been persisted.
                result = self._repository.store_cluster(request)
                if result is not None:
                    count += 1
            self._stored_count = count
            logger.info(
                "Successfully stored %d/%d cluster(s)", count, len(self._clusters)
            )
            self._phase = Phase.DONE
        except Exception as exc:
            logger.exception("store_cluster submission failed: %s", exc)
            self._error_message = str(exc)
            self._phase = Phase.ERROR
        finally:
            self._notify_phase_changed()

    @staticmethod
    def _build_request(
        cluster: ClusteredEventInfo,
        hdu_id: int,
        fits_id: int,
        label: ParticleType,
    ) -> ClusterStoreRequest:
        bb: BoundingBox = cluster.boundingBox
        return ClusterStoreRequest(
            data=cluster.data.tolist(),
            hdu_id=hdu_id,
            bounding_box={
                "top": int(bb.top),
                "left": int(bb.left),
                "bottom": int(bb.bottom),
                "right": int(bb.right),
            },
            sigma_x=float(cluster.sigmaX),
            sigma_y=float(cluster.sigmaY),
            total_energy=float(cluster.energy),
            total_pixels=int(cluster.pixelCount),
            fits_id=fits_id,
            classification=label.name,
        )
