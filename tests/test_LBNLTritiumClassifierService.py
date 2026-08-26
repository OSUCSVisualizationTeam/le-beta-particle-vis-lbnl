"""Tests for LBNLTritiumClassifierService (issue #54)."""

import threading

import numpy as np

from le_beta_vis.common.ClassifierDataClasses import ClassificationRequestCluster
from le_beta_vis.common.LBNLTritiumClassifierService import LBNLTritiumClassifierService


class _FakeConfig:
    def __init__(self, weights_dir="/nonexistent/weights/dir"):
        self._weights_dir = weights_dir

    def get(self, key, default=None):
        if key == "classifier:lbnl_model_weights_dir":
            return self._weights_dir
        return default

    def get_int(self, key, default, minimum=None, maximum=None):
        return default


class _FakeKerasModel:
    """Records the array it was called with, always predicts a fixed score per cluster."""

    def __init__(self, scores):
        self.scores = scores
        self.last_input = None

    def predict(self, x, verbose=0):
        self.last_input = x
        return np.array(self.scores[: len(x)])


class _FakeBdtModel:
    def __init__(self, scores):
        self.scores = scores
        self.last_input = None

    def predict_proba(self, x):
        self.last_input = x
        # sklearn's predict_proba shape is (n_samples, n_classes); column 1 is the positive class.
        return np.array([[1 - s, s] for s in self.scores[: len(x)]])


def _cluster(cluster_id: int, energy: float = 100.0) -> ClassificationRequestCluster:
    return ClassificationRequestCluster(
        data=[[0.0] * 10 for _ in range(10)],
        cluster_id=cluster_id,
        sigmaX=1.0,
        sigmaY=1.0,
        total_energy=energy,
        total_pixels=10,
    )


def _run_and_wait(classify_fn, clusters):
    done = threading.Event()
    captured = {}

    def on_complete(batch):
        captured["batch"] = batch
        done.set()

    def on_error(exc):
        captured["error"] = exc
        done.set()

    classify_fn(clusters, on_complete, on_error)
    assert done.wait(timeout=5.0)
    if "error" in captured:
        raise captured["error"]
    return captured["batch"]


def test_missing_weights_directory_leaves_all_three_models_unavailable():
    service = LBNLTritiumClassifierService(_FakeConfig())
    assert set(service.unavailable_models()) == {"CNN", "NRG", "BDT"}


def test_classify_with_unavailable_model_reports_all_clusters_failed_not_on_error():
    service = LBNLTritiumClassifierService(_FakeConfig())
    clusters = [_cluster(0), _cluster(1)]

    batch = _run_and_wait(service.classify_cnn, clusters)

    assert batch.total == 2
    assert batch.failed == 2
    assert all(r.score is None for r in batch.results)


def test_classify_cnn_applies_injected_model_and_normalization():
    fake_model = _FakeKerasModel(scores=[0.9, 0.1])
    service = LBNLTritiumClassifierService(
        _FakeConfig(),
        cnn_model=fake_model,
        cnn_meta={"normalize_threshold_low": 0.0, "normalize_threshold_high": 10.0},
    )
    clusters = [_cluster(0), _cluster(1)]

    batch = _run_and_wait(service.classify_cnn, clusters)

    assert batch.total == 2
    assert batch.failed == 0
    assert [r.cluster_id for r in batch.results] == [0, 1]
    assert batch.results[0].score.confidence == 0.9
    assert batch.results[1].score.confidence == 0.1
    # Input pixels (all 0.0) clipped to [0, 10] and rescaled to [0, 1] stay 0.0.
    assert fake_model.last_input.max() <= 1.0
    assert fake_model.last_input.min() >= 0.0
    assert fake_model.last_input.shape == (2, 10, 10, 1)


def test_classify_cnn_skips_non_10x10_cluster_without_failing_the_rest():
    """Regression test: an oversized crop (e.g. a muon track) must not poison classification
    for every other cluster in the same batch — it used to raise inside np.array() and fail
    the whole batch."""
    fake_model = _FakeKerasModel(scores=[0.8])
    service = LBNLTritiumClassifierService(
        _FakeConfig(),
        cnn_model=fake_model,
        cnn_meta={"normalize_threshold_low": 0.0, "normalize_threshold_high": 10.0},
    )
    normal_cluster = _cluster(0)
    muon_cluster = ClassificationRequestCluster(
        data=[[0.0] * 12 for _ in range(14)],  # not 10x10
        cluster_id=1,
        sigmaX=3.0,
        sigmaY=1.5,
        total_energy=5000.0,
        total_pixels=120,
    )

    batch = _run_and_wait(service.classify_cnn, [normal_cluster, muon_cluster])

    assert batch.total == 2
    assert batch.failed == 1
    assert batch.results[0].score is not None
    assert batch.results[0].score.confidence == 0.8
    assert batch.results[1].score is None
    # Only the conforming cluster ever reached the model.
    assert fake_model.last_input.shape[0] == 1


def test_classify_bdt_uses_energy_and_sigma_features():
    fake_model = _FakeBdtModel(scores=[0.7, 0.2])
    service = LBNLTritiumClassifierService(_FakeConfig(), bdt_model=fake_model)
    clusters = [_cluster(0, energy=500.0), _cluster(1, energy=50.0)]

    batch = _run_and_wait(service.classify_bdt, clusters)

    assert [r.score.confidence for r in batch.results] == [0.7, 0.2]
    assert list(fake_model.last_input.columns) == ["clusterEnergy", "clusterSigmaX", "clusterSigmaY"]
    assert fake_model.last_input["clusterEnergy"].tolist() == [500.0, 50.0]


def test_classify_nrg_applies_injected_model_via_real_point_cloud_prep():
    fake_model = _FakeKerasModel(scores=[0.6, 0.4])
    service = LBNLTritiumClassifierService(
        _FakeConfig(),
        nrg_model=fake_model,
        nrg_meta={
            "normalize_threshold_low": 0.0,
            "normalize_threshold_high": 2.0,
            "threshold": 0.01,
            "pixels_around_brightest_pixel": 5,
        },
    )
    data = [[0.0] * 10 for _ in range(10)]
    data[5][5] = 2.0
    clusters = [
        ClassificationRequestCluster(
            data=data, cluster_id=0, sigmaX=1.0, sigmaY=1.0, total_energy=2.0, total_pixels=1,
        ),
        ClassificationRequestCluster(
            data=data, cluster_id=1, sigmaX=1.0, sigmaY=1.0, total_energy=2.0, total_pixels=1,
        ),
    ]

    batch = _run_and_wait(service.classify_nrg, clusters)

    assert batch.total == 2
    assert batch.failed == 0
    assert [r.score.confidence for r in batch.results] == [0.6, 0.4]
    # GetPixelClusterData's output contract: (N, pixels_around_brightest_pixel, 3).
    assert fake_model.last_input.shape == (2, 5, 3)
