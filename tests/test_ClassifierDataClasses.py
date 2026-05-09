"""Tests for ClassifierDataClasses DTO conversions."""

from le_beta_vis.common.ClassifierDataClasses import (
    ClassificationRequest,
    ClassificationRequestCluster,
)


def test_request_round_trip_serialization():
    clusters = [
        ClassificationRequestCluster(
            data=[[1.0, 2.0], [3.0, 4.0]],
            cluster_id=7,
            sigmaX=1.2,
            sigmaY=2.4,
            total_energy=5.5,
            total_pixels=4,
        )
    ]
    request = ClassificationRequest(model="CNN", clusters=clusters)

    payload = request.to_classifier_dict()
    assert payload["Model"] == "CNN"
    assert isinstance(payload["Clusters"], list)
    assert payload["Clusters"][0]["cluster_id"] == 7

    parsed = ClassificationRequest.from_classifier_dict(payload)
    assert parsed.model == "CNN"
    assert len(parsed.clusters) == 1
    assert isinstance(parsed.clusters[0], ClassificationRequestCluster)
    assert parsed.clusters[0].cluster_id == 7
    assert parsed.clusters[0].sigmaX == 1.2
    assert parsed.clusters[0].total_pixels == 4


def test_cluster_from_dict_defaults():
    cluster = ClassificationRequestCluster.from_cluster_dict({})
    assert cluster.cluster_id == 0
    assert cluster.sigmaX == 0.0
    assert cluster.sigmaY == 0.0
    assert cluster.total_energy == 0.0
    assert cluster.total_pixels == 0
