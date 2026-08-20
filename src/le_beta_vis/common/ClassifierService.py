from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable

from le_beta_vis.common.ClassifierDataClasses import (
    ClassificationRequestCluster,
)
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


ErrorCallback = Callable[[Exception], None]
CompletionCallback = Callable[[ClassificationBatchResult], None]


@dataclass(frozen=True)
class ClusterScores:
    """Per-cluster ML confidence scores, one value per model.

    None for a model means that model failed for this cluster.
    """

    cnn: Optional[float]
    nrg: Optional[float]
    bdt: Optional[float]


class ClassifierService(ABC):
    """
    All classify_* methods are asynchronous. Callbacks fire from a background
    thread. ``ClassificationRequestCluster.data`` must be hydrated by the
    caller before passing clusters to any classify_* method.
    """

    @abstractmethod
    def classify_cnn(
        self,
        clusters: list[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    @abstractmethod
    def classify_nrg(
        self,
        clusters: list[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    @abstractmethod
    def classify_bdt(
        self,
        clusters: list[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    def unavailable_models(self) -> list[str]:
        """Names of models this instance could not load (e.g. missing weight files).

        Empty by default. A backend that loads real artifacts (e.g.
        LBNLTritiumClassifierService) overrides this so callers can surface a
        non-fatal degraded-mode warning without needing a dedicated
        readiness/status channel — see wiki/Front-Design-Startup-Readiness.md's
        pre-warm discussion for why this is a plain synchronous check rather
        than an EventEnvelope broadcast.
        """
        return []
