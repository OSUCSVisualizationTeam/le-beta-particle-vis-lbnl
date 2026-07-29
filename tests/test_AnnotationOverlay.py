"""Tests for the AnnotationOverlay domain object."""

from le_beta_vis.common.AnnotationOverlay import AnnotationOverlay
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster


class TestAnnotationOverlay:
    def test_positional_bounding_box_only(self):
        bbox = BoundingBox(0, 0, 10, 10)
        overlay = AnnotationOverlay(bbox)
        assert overlay.bounding_box == bbox
        assert overlay.cluster is None

    def test_with_cluster(self):
        bbox = BoundingBox(1, 2, 11, 12)
        cluster = Cluster(boundingBox=bbox, data=None, centerX=6, centerY=7)
        overlay = AnnotationOverlay(bbox, cluster=cluster)
        assert overlay.bounding_box == bbox
        assert overlay.cluster is cluster
