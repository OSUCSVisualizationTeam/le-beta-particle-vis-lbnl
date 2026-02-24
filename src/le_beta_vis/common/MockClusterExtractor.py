import logging
import threading
from typing import Callable, List, Optional

import numpy as np

from .BoundingBox import BoundingBox
from .ClusterExtractor import ClusteredEventInfo, ClusterExtractor

logger = logging.getLogger(__name__)


class MockClusterExtractor(ClusterExtractor):
    """Mock cluster extractor that simulates async work.

    Returns a single ClusteredEventInfo wrapping the entire
    input region after a configurable delay.
    """

    def __init__(self, delay_seconds: float = 0.25):
        self._delay = delay_seconds
        self._timer: Optional[threading.Timer] = None
        self._cancelled = False

    def extract(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        callback: Callable[[List[ClusteredEventInfo]], None],
        energyMinimum: Optional[float] = None,
        energyMaximum: Optional[float] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """Starts a simulated extraction after a short delay."""
        self._cancelled = False
        self._timer = threading.Timer(
            self._delay,
            self._finish,
            args=(data, bounding_box, callback),
        )
        self._timer.daemon = True
        self._timer.start()

    def cancel(self) -> None:
        """Cancels the pending extraction."""
        self._cancelled = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _finish(
        self,
        data: np.ndarray,
        bounding_box: BoundingBox,
        callback: Callable[[List[ClusteredEventInfo]], None],
    ) -> None:
        """Timer callback — builds the result and fires the callback."""
        try:
            if self._cancelled:
                return

            max_idx = int(np.argmax(data))
            max_row, max_col = np.unravel_index(max_idx, data.shape)
            center_y = bounding_box.top + int(max_row)
            center_x = bounding_box.left + int(max_col)

            event = ClusteredEventInfo(
                boundingBox=bounding_box,
                data=data.copy(),
                centerX=center_x,
                centerY=center_y,
            )
            callback([event])
        except Exception:
            logger.exception("Mock cluster extraction failed")
            if not self._cancelled:
                callback([])
