"""Real-socket integration tests for ZMQBasedEventRepository (issue #196, Layer 2).

``test_ZMQBasedEventRepository.py`` mocks ``zmq.Context``/``zmq.Socket``
entirely, so it can prove the repository *builds* the right request and
*parses* a given response, but it can never prove a request actually
survives real JSON serialization over a real socket -- which is exactly the
gap that let a numpy-int ``TypeError`` in ``socket.send_json()`` ship
unnoticed (see ``TestClusterStoreRequest`` in ``test_EPSDataClasses.py`` for
the dataclass-level contract this pins from the other side).

These tests instead drive a real ``ZMQBasedEventRepository`` against a real
``zmq.REP`` socket backed by an in-memory fake EPS (``tests/fake_eps_fixture.py``)
-- real thread, real IPC socket, real JSON on the wire, no mocking of the ZMQ
layer at all. Unlike ``tests/test_live_*.py``, this needs no external service
(no MySQL, no real ``EventPersistence`` process, no display server), so it is
NOT gated by ``LBNLVIS_LIVE_TESTS`` -- it runs in every default
``uv run pytest tests`` invocation, matching this issue's own "ZMQ in-process,
CI-compatible" framing.
"""

import numpy as np
import pytest
import zmq

from fake_eps_fixture import fake_eps  # noqa: F401
from mock_configuration_service import MockConfigurationService

from le_beta_vis.common.EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
)
from le_beta_vis.common.ZMQBasedEventRepository import ZMQBasedEventRepository

_NATIVE_KWARGS = dict(
    data=None,
    hdu_id=0,
    bounding_box={"top": 1, "left": 2, "bottom": 3, "right": 4},
    sigma_x=1.5,
    sigma_y=2.0,
    total_energy=100.0,
    total_pixels=25,
    fits_id=1,
    classification="TRITIUM",
)


class TestStoreClusterRoundTrip:

    def test_store_cluster_round_trip_through_real_socket(self, fake_eps):  # noqa: F811
        req = ClusterStoreRequest(**_NATIVE_KWARGS)

        cluster_id = fake_eps.repository.store_cluster(req)

        assert cluster_id == 1
        assert len(fake_eps.requests) == 1
        sent = fake_eps.requests[0]
        assert sent["Action"] == "Storage"
        assert sent["fits_id"] == 1
        assert sent["sigmaX"] == 1.5
        assert sent["sigmaY"] == 2.0
        assert sent["total_energy"] == 100.0
        assert sent["total_pixels"] == 25
        assert sent["classification"] == "TRITIUM"
        assert sent["bounding_box"] == {"top": 1, "left": 2, "bottom": 3, "right": 4}

    def test_second_store_cluster_gets_incrementing_id(self, fake_eps):  # noqa: F811
        req = ClusterStoreRequest(**_NATIVE_KWARGS)
        first_id = fake_eps.repository.store_cluster(req)
        second_id = fake_eps.repository.store_cluster(req)
        assert (first_id, second_id) == (1, 2)

    def test_eps_failure_response_returns_none(self, fake_eps):  # noqa: F811
        fake_eps.responses.put({"result": "failure", "cluster_id": None, "error": "boom"})
        req = ClusterStoreRequest(**_NATIVE_KWARGS)

        result = fake_eps.repository.store_cluster(req)

        assert result is None

    def test_non_serializable_field_raises_typeerror(self, fake_eps):  # noqa: F811
        """Pins current, documented behavior: ``_send`` does not catch ``TypeError`` from ``send_json`` (see the note in issue
        #196) -- this is not fixed here, just proven."""
        req = ClusterStoreRequest(**{**_NATIVE_KWARGS, "total_pixels": np.int64(25)})

        with pytest.raises(TypeError):
            fake_eps.repository.store_cluster(req)


class TestZmqTimeout:

    def test_zmq_timeout_returns_none(self, tmp_path):
        """No fake_eps fixture -- points at an endpoint nothing is listening on."""
        config = MockConfigurationService()
        config.set("eps:cluster_ipc", f"ipc://{tmp_path}/unbound.ipc")
        config.set("eps:timeout_ms", 300)
        repo = ZMQBasedEventRepository(config=config, context=zmq.Context())
        req = ClusterStoreRequest(**_NATIVE_KWARGS)

        result = repo.store_cluster(req)

        assert result is None


class TestUpdateClassificationRoundTrip:

    def test_update_classification_round_trip(self, fake_eps):  # noqa: F811
        req = ClassificationUpdateRequest(cluster_id=7, classification="muon")

        updated = fake_eps.repository.update_classification_sync(req)

        assert updated is True
        assert len(fake_eps.requests) == 1
        sent = fake_eps.requests[0]
        assert sent["Action"] == "UpdateClassification"
        assert sent["cluster_id"] == 7
        assert sent["classification"] == "muon"


class TestQueryClustersRoundTrip:

    def test_query_clusters_returns_seeded_clusters(self, fake_eps):  # noqa: F811
        fake_eps.responses.put({
            "result": "success",
            "clusters": [
                {
                    "fits_id": 1,
                    "hdu_id": 0,
                    "cluster_id": 10,
                    "bounding_box": {"top": 1, "left": 2, "bottom": 3, "right": 4},
                    "data": None,
                    "total_energy": 500.0,
                    "sigmaX": 1.5,
                    "sigmaY": 2.0,
                    "classification": "TRITIUM",
                    "total_pixels": 20,
                    "filename": "a.fits",
                    "date": "2026-01-01",
                },
            ],
        })

        clusters = fake_eps.repository.query_clusters_sync(ClusterQueryFilter(fits_id=1))

        assert len(clusters) == 1
        assert clusters[0].clusterId == 10
        assert clusters[0].fitsId == 1
        assert clusters[0].energy == 500.0
        assert fake_eps.requests[0]["Action"] == "Retrieval"
        assert fake_eps.requests[0]["fits_id"] == 1
