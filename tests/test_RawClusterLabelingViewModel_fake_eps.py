"""Real-socket integration test for RawClusterLabelingViewModel (issue #196, Gap A).

``test_RawClusterLabelingViewModel.py`` drives the ViewModel against a
``MagicMock()`` repository -- it can prove ``submit()`` calls
``store_cluster()`` with the right arguments, but never that those arguments
actually survive real JSON serialization over a real socket, which is
exactly the mechanism that let a numpy-int ``TypeError`` in
``socket.send_json()`` ship unnoticed in this ViewModel's flow (see that
file's ``test_build_request_converts_numpy_fields_to_json_serializable_natives``
for the dataclass-level half of this check).

This test instead drives a real ``RawClusterLabelingViewModel`` against the
in-process fake EPS from ``tests/fake_eps_fixture.py`` -- real thread, real
IPC socket, real JSON on the wire. No external services, so (like
``test_ZMQBasedEventRepository_fake_eps.py``) this is NOT gated by
``LBNLVIS_LIVE_TESTS`` -- it runs in every default ``uv run pytest tests``
invocation.
"""

import threading
from unittest.mock import MagicMock

import numpy as np

from fake_eps_fixture import fake_eps  # noqa: F401

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.frontend.viewmodels.RawClusterLabelingViewModel import (
    Phase,
    RawClusterLabelingViewModel,
)


def _numpy_typed_cluster() -> ClusteredEventInfo:
    """Mirrors what LBNLClassicalClusterExtractor actually hands off -- numpy scalars, not Python natives (see
    test_RawClusterLabelingViewModel.py's matching unit test for why)."""
    return ClusteredEventInfo(
        boundingBox=BoundingBox(
            top=np.int64(5), left=np.int64(10),
            bottom=np.int64(10), right=np.int64(15),
        ),
        data=np.ones((5, 5), dtype=float),
        centerX=np.int64(12), centerY=np.int64(7),
        sigmaX=np.float64(1.8), sigmaY=np.float64(1.4),
        energy=np.float64(3000.0), pixelCount=np.int64(30),
    )


def _submit_and_wait(vm: RawClusterLabelingViewModel) -> None:
    done = threading.Event()
    vm.add_phase_changed_callback(
        lambda: done.set() if vm.phase in (Phase.DONE, Phase.ERROR) else None
    )
    vm.submit()
    assert done.wait(timeout=5.0), "Timed out waiting for submission to finish"


def test_submit_with_numpy_typed_cluster_round_trips_through_real_socket(fake_eps):  # noqa: F811
    vm = RawClusterLabelingViewModel(
        clusters=[_numpy_typed_cluster()],
        repository=fake_eps.repository,
        physics=MagicMock(),
        fits_info_provider=lambda: (7, 2),
    )
    vm.set_label(0, ParticleType.TRITIUM)

    _submit_and_wait(vm)

    assert vm.phase == Phase.DONE
    assert vm.stored_count == 1
    assert vm.error_message is None

    assert len(fake_eps.requests) == 1
    sent = fake_eps.requests[0]
    assert sent["Action"] == "Storage"
    assert sent["fits_id"] == 7
    assert sent["hdu_id"] == 2
    assert sent["classification"] == "TRITIUM"
    assert sent["sigmaX"] == 1.8
    assert sent["sigmaY"] == 1.4
    assert sent["total_energy"] == 3000.0
    assert sent["total_pixels"] == 30
    assert sent["bounding_box"] == {"top": 5, "left": 10, "bottom": 10, "right": 15}
