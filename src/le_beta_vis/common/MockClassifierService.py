from typing import Optional
import time
import random
import threading
from le_beta_vis.common.ClassifierDataClasses import (
    ClassificationRequestCluster,
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

class MockClassifierService(ClassifierService):
    """Mock ClassifierService that simulates asynchronous classification of clusters."""
    def classify_cluster(
        self,
        clusters: list[ClassificationRequestCluster],
        model: str,
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        def _run() -> None:
            try:
                self.random_classification(
                    clusters=clusters,
                    on_complete=on_complete,
                    on_error=on_error,
                    model=model,
                )
            except Exception as exc:
                if on_error:
                    on_error(exc)

        threading.Thread(target=_run, daemon=True).start()
    
    def classify_cnn(
        self,
        clusters: list[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.classify_cluster(clusters, "CNN", on_complete, on_error)

    def classify_nrg(
        self,
        clusters: list[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.classify_cluster(clusters, "NRG", on_complete, on_error)

    def classify_bdt(
        self,
        clusters: list[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.classify_cluster(clusters, "BDT", on_complete, on_error)

    def random_classification(
        self,
        clusters: list[ClassificationRequestCluster],
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
            # simulate occasional model failures
            if rand_rating <= 0.05:
                result = ClassificationResult(cluster.cluster_id, model, None)
                failed += 1
            else:
                score = ClassificationScore(ParticleType.TRITIUM, rand_rating)
                result = ClassificationResult(cluster.cluster_id, model, score)
            total += 1
            classified_clusters.append(result)
        on_complete(ClassificationBatchResult(classified_clusters, total, failed))
