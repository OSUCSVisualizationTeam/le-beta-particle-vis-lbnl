from typing import Optional

import numpy as np

from .BoundingBox import BoundingBox
from .ClusterExtractor import ClusteredEventInfo


class Cluster(ClusteredEventInfo):
    """A cluster with persistence and classification metadata.

    Extends ``ClusteredEventInfo`` with fields needed by the
    backend persistence pipeline (FITS ID, cluster ID, ML
    classification scores).  Persistence **methods** (MySQL, HTTP)
    remain in the backend; this class is a pure data model.

    Attributes:
        fitsId (Optional[int]): Foreign key to the originating
            FITS capture.
        clusterId (Optional[int]): Unique cluster identifier
            within the FITS capture.
        cnnClassification (float): CNN tritium confidence score
            (0.0–1.0).
        nrgClassification (float): Energy-based tritium confidence
            score (0.0–1.0).
        bdtClassification (float): BDT tritium confidence score
            (0.0–1.0).
    """

    def __init__(
        self,
        boundingBox: BoundingBox,
        data: np.ndarray,
        centerX: int,
        centerY: int,
        sigmaX: float = 0.0,
        sigmaY: float = 0.0,
        energy: float = 0.0,
        fitsFilename: Optional[str] = None,
        date: Optional[str] = None,
        pixelCount: int = 0,
        fitsId: Optional[int] = None,
        clusterId: Optional[int] = None,
        cnnClassification: float = 0.0,
        nrgClassification: float = 0.0,
        bdtClassification: float = 0.0,
        classification: str = "UNCLASSIFIED",
    ):
        super().__init__(
            boundingBox=boundingBox,
            data=data,
            centerX=centerX,
            centerY=centerY,
            sigmaX=sigmaX,
            sigmaY=sigmaY,
            energy=energy,
            pixelCount=pixelCount,
        )
        self.fitsId = fitsId
        self.clusterId = clusterId
        self.cnnClassification = cnnClassification
        self.nrgClassification = nrgClassification
        self.bdtClassification = bdtClassification
        self.fitsFilename = fitsFilename
        self.date = date
        self.classification = classification
