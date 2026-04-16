from typing import List, Optional, Callable

import numpy as np

from .BoundingBox import BoundingBox
from .Cluster import Cluster
from .EPSDataClasses import ClusterQueryFilter
from .EventRepository import EventRepository


def _gaussian_blob(
    rows: int, cols: int, cx: int, cy: int,
    sigma_x: float, sigma_y: float, amplitude: float,
) -> np.ndarray:
    """Generates a 2-D Gaussian blob centred at (cy, cx)."""
    y = np.arange(rows)
    x = np.arange(cols)
    xx, yy = np.meshgrid(x, y)
    sx = max(sigma_x, 0.5)
    sy = max(sigma_y, 0.5)
    blob = amplitude * np.exp(
        -(((xx - cx) ** 2) / (2 * sx ** 2)
          + ((yy - cy) ** 2) / (2 * sy ** 2))
    )
    return blob


# Each tuple: (width, height, cx_rel, cy_rel, sigmaX, sigmaY,
#              energy, pixelCount, cnn, nrg, bdt, fitsId, clusterId)
_MOCK_SPECS = [
    (12, 10, 6, 5, 1.8, 1.5, 3200.0, 42, 0.95, 0.91, 0.88, 1, 1),
    (8, 8, 4, 4, 1.2, 1.3, 1800.0, 28, 0.87, 0.82, 0.79, 1, 2),
    (15, 12, 7, 6, 2.5, 2.1, 5400.0, 65, 0.92, 0.88, 0.90, 1, 3),
    (10, 10, 5, 5, 1.5, 1.4, 2600.0, 35, 0.78, 0.81, 0.76, 2, 4),
    (6, 6, 3, 3, 0.9, 0.8, 900.0, 15, 0.60, 0.55, 0.58, 2, 5),
    (20, 18, 10, 9, 3.2, 2.8, 8200.0, 110, 0.45, 0.50, 0.42, 2, 6),
    (9, 7, 4, 3, 1.1, 1.0, 1500.0, 22, 0.30, 0.28, 0.35, 3, 7),
    (14, 11, 7, 5, 2.0, 1.8, 4100.0, 55, 0.99, 0.97, 0.96, 3, 8),
    (7, 7, 3, 3, 1.0, 1.0, 1100.0, 18, 0.72, 0.68, 0.74, 3, 9),
    (11, 9, 5, 4, 1.6, 1.4, 2900.0, 38, 0.83, 0.80, 0.85, 4, 10),
    (16, 14, 8, 7, 2.8, 2.4, 6700.0, 85, 0.15, 0.20, 0.18, 4, 11),
    (5, 5, 2, 2, 0.7, 0.6, 600.0, 10, 0.88, 0.90, 0.86, 5, 12),
]


class MockEventRepository(EventRepository):
    """Returns synthetic Cluster objects for UI development.

    Generates ~12 clusters with varied classification scores,
    energies, and sizes to exercise all visual states in the
    Event Grid and Detail Inspector.
    """

    def fetch_events(
            self,
            callback: Callable,
            on_error: Callable,
    ) -> None:
        """Returns a list of synthetic Cluster objects."""
        clusters: List[Cluster] = []
        for spec in _MOCK_SPECS:
            (w, h, cx_rel, cy_rel, sx, sy,
             energy, px, cnn, nrg, bdt, fits_id, cid) = spec
            data = _gaussian_blob(h, w, cx_rel, cy_rel, sx, sy, energy / px)
            bbox = BoundingBox(
                top=cy_rel * 10,
                left=cx_rel * 10,
                bottom=cy_rel * 10 + h,
                right=cx_rel * 10 + w,
            )
            cluster = Cluster(
                boundingBox=bbox,
                data=data,
                centerX=bbox.left + cx_rel,
                centerY=bbox.top + cy_rel,
                sigmaX=sx,
                sigmaY=sy,
                energy=energy,
                pixelCount=px,
                fitsId=fits_id,
                clusterId=cid,
                cnnClassification=cnn,
                nrgClassification=nrg,
                bdtClassification=bdt,
            )
            clusters.append(cluster)
        callback(clusters)

    def query_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        callback: Callable,
        on_error: Callable,
    ) -> None:
        """Returns synthetic clusters, optionally filtered.

        Applies Python-side filtering to match EPS behaviour.
        """
        def _filter_and_forward(clusters: List[Cluster]) -> None:
            if query_filter is None:
                callback(clusters)
                return
            filtered_clusters = [c for c in clusters if self._matches(c, query_filter)]
            callback(filtered_clusters)

        self.fetch_events(callback=_filter_and_forward, on_error=on_error)

    @staticmethod
    def _matches(
        cluster: Cluster, qf: ClusterQueryFilter
    ) -> bool:
        """Returns True if *cluster* satisfies all filter criteria."""
        if qf.cluster_id is not None and cluster.clusterId != qf.cluster_id:
            return False
        if qf.fits_id is not None and cluster.fitsId != qf.fits_id:
            return False
        if qf.min_sigma_x is not None and cluster.sigmaX < qf.min_sigma_x:
            return False
        if qf.min_sigma_y is not None and cluster.sigmaY < qf.min_sigma_y:
            return False
        if (
            qf.min_total_energy is not None
            and cluster.energy < qf.min_total_energy
        ):
            return False
        if (
            qf.min_total_pixels is not None
            and cluster.pixelCount < qf.min_total_pixels
        ):
            return False
        if qf.classification is not None:
            return False
        return True
