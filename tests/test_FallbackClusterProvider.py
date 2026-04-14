"""Tests for FallbackClusterProvider paginated cursor behavior."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.livemode.FallbackClusterProvider import (
    FallbackClusterProvider,
)


def _make_cluster(cid: int) -> Cluster:
    return Cluster(
        boundingBox=BoundingBox(top=0, left=0, bottom=1, right=1),
        data=None,
        centerX=None,
        centerY=None,
        sigmaX=1.0,
        sigmaY=1.0,
        energy=1.0,
        pixelCount=1,
        fitsFilename="f.fits",
        date="2026-04-14",
        fitsId=1,
        clusterId=cid,
        classification="tritium",
        cnnClassification=0.0,
        nrgClassification=0.0,
        bdtClassification=0.0,
        hdu_id=0,
    )


class TestFallbackClusterProviderPagination(unittest.TestCase):
    def test_first_fetch_uses_offset_zero(self) -> None:
        repo = MagicMock()
        repo.query_recent_clusters.return_value = [
            _make_cluster(i) for i in range(5)
        ]

        provider = FallbackClusterProvider(repo)
        provider.fetch(5)

        repo.query_recent_clusters.assert_called_once_with(limit=5, offset=0)

    def test_successive_fetches_advance_offset(self) -> None:
        repo = MagicMock()
        repo.query_recent_clusters.side_effect = [
            [_make_cluster(i) for i in range(5)],
            [_make_cluster(i) for i in range(5, 10)],
        ]

        provider = FallbackClusterProvider(repo)
        provider.fetch(5)
        provider.fetch(5)

        self.assertEqual(
            repo.query_recent_clusters.call_args_list[0].kwargs,
            {"limit": 5, "offset": 0},
        )
        self.assertEqual(
            repo.query_recent_clusters.call_args_list[1].kwargs,
            {"limit": 5, "offset": 5},
        )

    def test_partial_result_wraps_and_tops_up(self) -> None:
        """When DB is exhausted, cursor resets to 0 and fills the rest."""
        repo = MagicMock()
        repo.query_recent_clusters.side_effect = [
            [_make_cluster(10), _make_cluster(11)],  # only 2 of 5 available
            [_make_cluster(0), _make_cluster(1), _make_cluster(2)],  # wrapped
        ]

        provider = FallbackClusterProvider(repo)
        result = provider.fetch(5)

        self.assertEqual(len(result), 5)
        self.assertEqual(
            [c.clusterId for c in result],
            [10, 11, 0, 1, 2],
        )
        self.assertEqual(
            repo.query_recent_clusters.call_args_list[0].kwargs,
            {"limit": 5, "offset": 0},
        )
        self.assertEqual(
            repo.query_recent_clusters.call_args_list[1].kwargs,
            {"limit": 3, "offset": 0},
        )

    def test_next_fetch_after_wrap_starts_from_post_wrap_offset(self) -> None:
        repo = MagicMock()
        repo.query_recent_clusters.side_effect = [
            [_make_cluster(10), _make_cluster(11)],
            [_make_cluster(0), _make_cluster(1), _make_cluster(2)],
            [_make_cluster(3), _make_cluster(4)],
        ]

        provider = FallbackClusterProvider(repo)
        provider.fetch(5)
        provider.fetch(2)

        self.assertEqual(
            repo.query_recent_clusters.call_args_list[2].kwargs,
            {"limit": 2, "offset": 3},
        )

    def test_zero_count_returns_empty_without_query(self) -> None:
        repo = MagicMock()
        provider = FallbackClusterProvider(repo)

        self.assertEqual(provider.fetch(0), [])
        repo.query_recent_clusters.assert_not_called()

    def test_repository_exception_returns_empty(self) -> None:
        repo = MagicMock()
        repo.query_recent_clusters.side_effect = RuntimeError("zmq dead")

        provider = FallbackClusterProvider(repo)

        self.assertEqual(provider.fetch(5), [])


if __name__ == "__main__":
    unittest.main()
