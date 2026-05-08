from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable
import time
import random
import threading
from le_beta_vis.common import (
    Cluster
)
from le_beta_vis.common.ParticleType import (
    ParticleType
)
from le_beta_vis.common.ClassifierService import (
    ClassificationScore,
    ClassificationResult,
    ClassificationBatchResult,
    ClassifierService,
    CompletionCallback,
    ErrorCallback
)
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)

class MockClassifierService(ClassifierService):
    """Mock ClassifierService that simulates asynchronous classification of clusters."""
    def __init__(self):
        self._on_error_callbacks = ErrorCallback
        self._on_completion_callback = CompletionCallback

    def classify_cluster(
        self,
        clusters: list[Cluster],
        model: str
    ) -> None:
        self._thread = threading.Thread(
            self.random_classification,
            args=(clusters, self._on_completion_callback, self.self._on_error_callbacks, model),
        )
        self._thread.daemon = True
        self._thread.start()

    def classify_cnn(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.classify_cluster(clusters, "CNN")

    def classify_nrg(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.classify_cluster(clusters, "NRG")

    def classify_bdt(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.classify_cluster(clusters, "BDT")

    def random_classification(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        model: str,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        #simulated delay
        classified_clusters = []
        failed = 0
        total = 0
        time.sleep(.2)
        for cluster in clusters:
            rand_rating = random.random()
            #if random float is divisble by .05, use that as an example without a score
            if rand_rating % .05 == 0:
                result = ClassificationResult(cluster.clusterId, model, None)
                failed += 1
            else:
                score = ClassificationScore(ParticleType("TRITIUM"), rand_rating)
                result = ClassificationResult(cluster.clusterId, model, score)
            total += 1
            classified_clusters.append(result)
        on_complete(ClassificationBatchResult(classified_clusters, total, failed))
