"""Unit tests for FreshClusterProvider and FallbackClusterProvider."""

import pytest
from unittest.mock import MagicMock, call

import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.EventEnvelope import EventEnvelope
from le_beta_vis.common.MockEventRepository import MockEventRepository
from le_beta_vis.frontend.livemode.FallbackClusterProvider import (
    FallbackClusterProvider,
)
from le_beta_vis.frontend.livemode.FreshClusterProvider import (
    FreshClusterProvider,
)


def _make_cluster(
    cluster_id: int = 0,
    date: str = None,
) -> Cluster:
    """Creates a minimal Cluster for testing."""
    return Cluster(
        boundingBox=BoundingBox(top=0, left=0, bottom=4, right=4),
        data=np.zeros((4, 4), dtype=np.float32),
        centerX=2,
        centerY=2,
        energy=1000.0,
        clusterId=cluster_id,
        date=date,
    )


def _make_envelope(payload: dict = None) -> EventEnvelope:
    """Creates a cluster.classified EventEnvelope."""
    return EventEnvelope(
        name="cluster.classified",
        payload=payload or {
            "sigmaX": 1.5,
            "sigmaY": 1.2,
            "total_energy": 2500.0,
            "fits_id": 42,
            "cluster_id": 7,
            "hdu_id": 3,
            "cnn_classification": 0.95,
            "nrg_classification": 0.88,
            "bdt_classification": 0.91,
            "classification": "TRITIUM",
        },
    )


# =====================================================================
# FreshClusterProvider
# =====================================================================


class TestFreshActivation:
    def test_activate_registers_callback(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)

        provider.activate()

        handler.register_callback.assert_called_once()
        args = handler.register_callback.call_args
        assert args[0][0] == "cluster.classified"

    def test_activate_idempotent(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)

        provider.activate()
        provider.activate()

        assert handler.register_callback.call_count == 1

    def test_deactivate_unregisters(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)

        provider.activate()
        provider.deactivate()

        handler.unregister.assert_called_once_with("uuid-1")

    def test_deactivate_noop_when_inactive(self):
        handler = MagicMock()
        provider = FreshClusterProvider(handler)

        provider.deactivate()  # should not raise

        handler.unregister.assert_not_called()


class TestFreshFetch:
    def _provider_with_events(self, n: int) -> FreshClusterProvider:
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)
        provider.activate()
        callback = handler.register_callback.call_args[0][1]
        for _ in range(n):
            callback(_make_envelope())
        return provider

    def test_fetch_drains_fifo(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)
        provider.activate()
        callback = handler.register_callback.call_args[0][1]

        e1 = _make_envelope({"sigmaX": 1.0, "sigmaY": 1.0,
                             "total_energy": 100.0, "cluster_id": 1})
        e2 = _make_envelope({"sigmaX": 2.0, "sigmaY": 2.0,
                             "total_energy": 200.0, "cluster_id": 2})
        callback(e1)
        callback(e2)

        result = provider.fetch(10)
        assert len(result) == 2
        assert result[0].clusterId == 1
        assert result[1].clusterId == 2

    def test_fetch_respects_count(self):
        provider = self._provider_with_events(5)
        result = provider.fetch(3)
        assert len(result) == 3
        assert provider.available == 2

    def test_fetch_empty_buffer(self):
        handler = MagicMock()
        provider = FreshClusterProvider(handler)
        assert provider.fetch(10) == []

    def test_available_reflects_buffer_size(self):
        provider = self._provider_with_events(4)
        assert provider.available == 4
        provider.fetch(2)
        assert provider.available == 2


class TestFreshPayloadConversion:
    def test_converts_payload_fields(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)
        provider.activate()
        callback = handler.register_callback.call_args[0][1]
        callback(_make_envelope())

        clusters = provider.fetch(1)
        c = clusters[0]

        assert c.sigmaX == 1.5
        assert c.sigmaY == 1.2
        assert c.energy == 2500.0
        assert c.fitsId == 42
        assert c.clusterId == 7
        assert c.hdu_id == 3
        assert c.cnnClassification == 0.95
        assert c.nrgClassification == 0.88
        assert c.bdtClassification == 0.91
        assert c.classification == "TRITIUM"

    def test_data_is_none(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)
        provider.activate()
        callback = handler.register_callback.call_args[0][1]
        callback(_make_envelope())

        clusters = provider.fetch(1)
        assert clusters[0].data is None

    def test_bounding_box_from_sigma(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)
        provider.activate()
        callback = handler.register_callback.call_args[0][1]
        callback(_make_envelope({"sigmaX": 2.0, "sigmaY": 3.0}))

        clusters = provider.fetch(1)
        bb = clusters[0].boundingBox
        assert bb.right == max(6, int(2.0 * 4 + 2))
        assert bb.bottom == max(6, int(3.0 * 4 + 2))

    def test_bad_payload_does_not_raise(self):
        handler = MagicMock()
        handler.register_callback.return_value = "uuid-1"
        provider = FreshClusterProvider(handler)
        provider.activate()
        callback = handler.register_callback.call_args[0][1]

        bad_envelope = EventEnvelope(
            name="cluster.classified",
            payload={"sigmaX": "not_a_number"},
        )
        callback(bad_envelope)

        assert provider.fetch(10) == []


# =====================================================================
# FallbackClusterProvider
# =====================================================================
#
# Pagination/wrap-around behavior lives in tests/test_FallbackClusterProvider.py.
# The only remaining check here is the MockEventRepository integration.


class TestFallbackFetch:
    def test_uses_mock_event_repository(self):
        """Integration test with the actual MockEventRepository."""
        repo = MockEventRepository()
        provider = FallbackClusterProvider(repo)
        result = provider.fetch(5)
        assert len(result) == 5
        for c in result:
            assert isinstance(c, Cluster)
