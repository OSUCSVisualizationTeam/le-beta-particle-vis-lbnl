"""Tests for the MockClassifierService."""

import random
import threading
import time

from le_beta_vis.common.ClassifierDataClasses import ClassificationRequestCluster
from le_beta_vis.common.MockClassifierService import MockClassifierService
from le_beta_vis.common.ParticleType import ParticleType


def _cluster(cluster_id: int) -> ClassificationRequestCluster:
    return ClassificationRequestCluster(
        data=[[0.0, 0.0], [0.0, 0.0]],
        cluster_id=cluster_id,
        sigmaX=0.0,
        sigmaY=0.0,
        total_energy=0.0,
        total_pixels=4,
    )


def test_random_classification_counts(monkeypatch):
    service = MockClassifierService()
    ratings = iter([0.0, 0.2, 0.03])
    monkeypatch.setattr(random, "random", lambda: next(ratings))
    monkeypatch.setattr(time, "sleep", lambda _: None)

    captured = {}

    def on_complete(batch):
        captured["batch"] = batch

    service.random_classification(
        clusters=[_cluster(1), _cluster(2), _cluster(3)],
        on_complete=on_complete,
        model="CNN",
    )

    batch = captured["batch"]
    assert batch.total == 3
    assert batch.failed == 2
    assert [r.cluster_id for r in batch.results] == [1, 2, 3]
    assert batch.results[0].score is None
    assert batch.results[1].score is not None
    assert batch.results[1].score.particle_type == ParticleType.TRITIUM
    assert batch.results[1].score.confidence == 0.2


def test_classify_cnn_invokes_callback(monkeypatch):
    service = MockClassifierService()
    monkeypatch.setattr(random, "random", lambda: 0.2)
    monkeypatch.setattr(time, "sleep", lambda _: None)

    done = threading.Event()

    def on_complete(batch):
        assert batch.total == 1
        done.set()

    service.classify_cnn([_cluster(99)], on_complete)

    assert done.wait(timeout=1.0)
