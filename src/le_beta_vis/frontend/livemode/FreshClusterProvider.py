"""Live-event cluster provider for the Live Mode screensaver.

Subscribes to the EventHandler for ``cluster.classified`` events
and converts each ``EventEnvelope`` payload into a ``Cluster``
with metadata only (``data=None``).  Actual pixel data is loaded
asynchronously by the ViewModel via ``ThumbnailLoaderService``
after clusters enter the display queue.
"""

import collections
import logging
import threading
from typing import Deque, List, Optional

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterProvider import ClusterBatch, ClusterProvider
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.EventHandlerInterface import EventHandlerInterface

logger = logging.getLogger(__name__)

_EVENT_NAME = "cluster.classified"
_DEFAULT_BUFFER_CAPACITY = 2000


class FreshClusterProvider(ClusterProvider):
    """ClusterProvider backed by live EventHandler subscriptions.

    Maintains an internal bounded deque fed by the
    ``cluster.classified`` callback.  The ViewModel polls
    ``fetch(n)`` on each advance tick to drain available clusters
    without exposing the deque directly.

    Clusters are constructed with ``data=None`` — the payload
    carries ``fits_id`` and ``cluster_id`` so real pixel data can
    be extracted later from the originating FITS HDU via
    ``ThumbnailLoaderService``.

    Args:
        event_handler: The pub/sub bus to subscribe to.
        buffer_capacity: Maximum clusters held before the oldest
            are dropped.
    """

    def __init__(
        self,
        event_handler: EventHandlerInterface,
        buffer_capacity: int = _DEFAULT_BUFFER_CAPACITY,
    ) -> None:
        self._event_handler = event_handler
        self._buffer: Deque[Cluster] = collections.deque(
            maxlen=buffer_capacity,
        )
        self._lock = threading.Lock()
        self._callback_id: Optional[str] = None

    # --- Lifecycle ---

    def activate(self) -> None:
        """Subscribe to the EventHandler for live cluster events.

        Idempotent — safe to call multiple times.
        """
        if self._callback_id is not None:
            return
        self._callback_id = self._event_handler.register_callback(
            _EVENT_NAME,
            self._on_cluster_event,
        )
        logger.info(
            "FreshClusterProvider activated, subscribed to %s",
            _EVENT_NAME,
        )

    def deactivate(self) -> None:
        """Unsubscribe from the EventHandler.

        Idempotent — safe to call when not active.
        """
        if self._callback_id is None:
            return
        self._event_handler.unregister(self._callback_id)
        self._callback_id = None
        logger.info("FreshClusterProvider deactivated")

    # --- ClusterProvider ---

    def fetch(self, count: int) -> ClusterBatch:
        """Dequeue up to ``count`` clusters from the internal buffer.

        Clusters are returned in FIFO order (oldest first).  The
        dequeued clusters are removed from the buffer.

        Args:
            count: Maximum number of clusters to return.

        Returns:
            A list of at most ``count`` clusters.
        """
        result: List[Cluster] = []
        with self._lock:
            while self._buffer and len(result) < count:
                result.append(self._buffer.popleft())
        return result

    @property
    def available(self) -> int:
        """Number of clusters currently buffered."""
        with self._lock:
            return len(self._buffer)

    # --- EventHandler callback (worker thread) ---

    def _on_cluster_event(self, envelope: EventEnvelope) -> None:
        """Receives cluster.classified envelopes from EventHandler.

        Converts the payload to a ``Cluster`` (with ``data=None``)
        and appends to the internal buffer.  Called on the
        EventHandler worker thread.
        """
        try:
            cluster = self._cluster_from_payload(envelope.payload)
            with self._lock:
                self._buffer.append(cluster)
        except Exception:
            logger.exception(
                "FreshClusterProvider: error processing envelope",
            )

    @staticmethod
    def _cluster_from_payload(payload: dict) -> Cluster:
        """Reconstruct a Cluster from an EventEnvelope payload.

        Creates a metadata-only Cluster with ``data=None``.
        Real pixel data is loaded later by the ViewModel via
        ``ThumbnailLoaderService.request_cluster_data()``.

        Args:
            payload: The ``EventEnvelope.payload`` dict for a
                ``cluster.classified`` event.

        Returns:
            A ``Cluster`` with metadata fields populated and
            ``data=None``.
        """
        sx = float(payload.get("sigmaX", 1.5))
        sy = float(payload.get("sigmaY", 1.5))
        w = max(6, int(sx * 4 + 2))
        h = max(6, int(sy * 4 + 2))
        cx, cy = w // 2, h // 2
        energy = float(payload.get("total_energy", 1000.0))

        return Cluster(
            boundingBox=BoundingBox(top=0, left=0, bottom=h, right=w),
            data=None,
            centerX=cx,
            centerY=cy,
            sigmaX=sx,
            sigmaY=sy,
            energy=energy,
            pixelCount=max(1, w * h // 4),
            fitsId=payload.get("fits_id"),
            clusterId=payload.get("cluster_id"),
            hdu_id=payload.get("hdu_id"),
            cnnClassification=float(
                payload.get("cnn_classification", 0.0),
            ),
            nrgClassification=float(
                payload.get("nrg_classification", 0.0),
            ),
            bdtClassification=float(
                payload.get("bdt_classification", 0.0),
            ),
            classification=str(
                payload.get("classification", "UNCLASSIFIED"),
            ),
        )
