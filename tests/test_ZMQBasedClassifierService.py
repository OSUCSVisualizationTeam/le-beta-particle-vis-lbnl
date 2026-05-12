"""Tests for ZMQBasedClassifierServer routing and parsing."""

from le_beta_vis.backend.ZMQBasedClassifierServer import ZMQBasedClassifierServer
from le_beta_vis.common.ClassifierDataClasses import ClassificationRequest
from le_beta_vis.common.ClassifierService import (
    ClassificationBatchResult,
    ClassificationResult,
    ClassificationScore,
    ClassifierService,
)
from le_beta_vis.common.ParticleType import ParticleType


class _SocketStub:
    def __init__(self):
        self.sent = []

    def send_json(self, payload):
        self.sent.append(payload)


class _ConfigStub:
    def get(self, _key):
        return None


class _RecordingClassifier(ClassifierService):
    def __init__(self):
        self.calls = []

    def _emit(self, model, clusters, on_complete):
        results = []
        for cluster in clusters:
            score = ClassificationScore(ParticleType.TRITIUM, 0.9)
            results.append(
                ClassificationResult(cluster.cluster_id, model, score)
            )
        on_complete(
            ClassificationBatchResult(results, len(results), 0)
        )

    def classify_cnn(self, clusters, on_complete, on_error=None):
        self.calls.append(("CNN", clusters))
        self._emit("CNN", clusters, on_complete)

    def classify_nrg(self, clusters, on_complete, on_error=None):
        self.calls.append(("NRG", clusters))
        self._emit("NRG", clusters, on_complete)

    def classify_bdt(self, clusters, on_complete, on_error=None):
        self.calls.append(("BDT", clusters))
        self._emit("BDT", clusters, on_complete)


def _make_service(classifier):
    return ZMQBasedClassifierServer(
        config=_ConfigStub(),
        classifier=classifier,
        auto_start=False,
    )


def test_classify_event_requires_model():
    classifier = _RecordingClassifier()
    service = _make_service(classifier)
    socket = _SocketStub()

    request = ClassificationRequest(model="", clusters=[])
    service.classify_event(request, socket)

    assert socket.sent
    assert socket.sent[0]["result"] == "failure"
    assert "model" not in socket.sent[0]
    assert classifier.calls == []


def test_classify_event_rejects_unknown_model():
    classifier = _RecordingClassifier()
    service = _make_service(classifier)
    socket = _SocketStub()

    request = ClassificationRequest(model="unknown", clusters=[])
    service.classify_event(request, socket)

    assert socket.sent
    assert socket.sent[0]["result"] == "failure"
    assert classifier.calls == []


def test_classify_event_routes_and_converts_clusters():
    classifier = _RecordingClassifier()
    service = _make_service(classifier)
    socket = _SocketStub()

    request_payload = {
        "Model": "cnn",
        "Clusters": [
            {
                "data": [[1.0, 2.0], [3.0, 4.0]],
                "cluster_id": 5,
                "sigmaX": 1.1,
                "sigmaY": 2.2,
                "total_energy": 4.4,
                "total_pixels": 4,
            }
        ],
    }
    request = ClassificationRequest.from_classifier_dict(request_payload)

    service.classify_event(request, socket)

    assert classifier.calls
    model, clusters = classifier.calls[0]
    assert model == "CNN"
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.cluster_id == 5
    assert cluster.sigmaX == 1.1
    assert cluster.sigmaY == 2.2
    assert cluster.total_energy == 4.4
    assert cluster.total_pixels == 4
    assert cluster.data == [[1.0, 2.0], [3.0, 4.0]]

    assert socket.sent
    response = socket.sent[0]
    assert response["total"] == 1
    assert response["failed"] == 0
    assert response["classifications"]["results"][0]["cluster_id"] == 5
    assert response["classifications"]["results"][0]["score"]["particle_type"] == "TRITIUM"
