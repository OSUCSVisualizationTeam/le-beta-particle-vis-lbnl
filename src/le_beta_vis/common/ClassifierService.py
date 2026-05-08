from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable

from le_beta_vis.common import Cluster
from le_beta_vis.common.ParticleType import ParticleType

@dataclass
class ClassificationScore:
    particle_type: ParticleType   # existing enum
    confidence: float             # 0.0–1.0

@dataclass
class ClassificationResult:
    cluster_id: int
    model: str                            # "cnn" | "nrg" | "bdt"
    score: Optional[ClassificationScore]  # None if this cluster failed to classify

@dataclass
class ClassificationBatchResult:
    results: list[ClassificationResult]  # order guaranteed to match input clusters
    total: int
    failed: int

ErrorCallback      = Callable[[Exception], None]
CompletionCallback = Callable[[ClassificationBatchResult], None]

class ClassifierService(ABC):
    """
    All classify_* methods are asynchronous. Callbacks fire from a background
    thread. Cluster.data must be hydrated by the caller before passing
    clusters to any classify_* method.
    """

    @abstractmethod
    def classify_cnn(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    @abstractmethod
    def classify_nrg(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    @abstractmethod
    def classify_bdt(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...
