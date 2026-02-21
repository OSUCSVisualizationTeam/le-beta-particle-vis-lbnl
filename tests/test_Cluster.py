"""Tests for the Cluster data model."""

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo


class TestCluster:
    def test_inherits_from_clustered_event_info(self):
        bbox = BoundingBox(0, 0, 10, 10)
        data = np.zeros((10, 10))
        cluster = Cluster(boundingBox=bbox, data=data, centerX=5, centerY=5)
        assert isinstance(cluster, ClusteredEventInfo)

    def test_base_fields_set(self):
        bbox = BoundingBox(1, 2, 11, 12)
        data = np.ones((10, 10))
        cluster = Cluster(
            boundingBox=bbox, data=data, centerX=7, centerY=6,
        )
        assert cluster.boundingBox == bbox
        assert cluster.centerX == 7
        assert cluster.centerY == 6
        assert cluster.data is data

    def test_classification_defaults(self):
        bbox = BoundingBox(0, 0, 10, 10)
        data = np.zeros((10, 10))
        cluster = Cluster(boundingBox=bbox, data=data, centerX=5, centerY=5)
        assert cluster.fitsId is None
        assert cluster.clusterId is None
        assert cluster.cnnClassification == 0
        assert cluster.nrgClassification == 0
        assert cluster.bdtClassification == 0

    def test_classification_fields_set(self):
        bbox = BoundingBox(0, 0, 10, 10)
        data = np.zeros((10, 10))
        cluster = Cluster(
            boundingBox=bbox, data=data, centerX=5, centerY=5,
            fitsId=42, clusterId=7,
            cnnClassification=1, nrgClassification=2,
            bdtClassification=3,
        )
        assert cluster.fitsId == 42
        assert cluster.clusterId == 7
        assert cluster.cnnClassification == 1
        assert cluster.nrgClassification == 2
        assert cluster.bdtClassification == 3

    def test_new_base_fields_default_to_zero(self):
        bbox = BoundingBox(0, 0, 10, 10)
        data = np.zeros((10, 10))
        cluster = Cluster(boundingBox=bbox, data=data, centerX=5, centerY=5)
        assert cluster.sigmaX == 0.0
        assert cluster.sigmaY == 0.0
        assert cluster.energy == 0.0
        assert cluster.pixelCount == 0
