"""Unit tests for RawClusterLabelingViewModel (no QApplication required)."""

import json
import threading
from typing import List, Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.ClusterExtractor import ClusteredEventInfo
from le_beta_vis.common.EPSDataClasses import ClusterStoreRequest
from le_beta_vis.common.ParticleType import ParticleType
from le_beta_vis.frontend.viewmodels.RawClusterLabelingViewModel import (
    Phase,
    RawClusterLabelingViewModel,
)


def _make_cluster(
    energy: float = 1000.0,
    sigma_x: float = 1.5,
    sigma_y: float = 1.2,
    pixel_count: int = 20,
    top: int = 0,
    left: int = 0,
) -> ClusteredEventInfo:
    return ClusteredEventInfo(
        boundingBox=BoundingBox(top=top, left=left, bottom=top + 5, right=left + 5),
        data=np.ones((5, 5), dtype=float),
        centerX=left + 2,
        centerY=top + 2,
        sigmaX=sigma_x,
        sigmaY=sigma_y,
        energy=energy,
        pixelCount=pixel_count,
    )


def _make_vm(
    clusters: Optional[List[ClusteredEventInfo]] = None,
    store_return: Optional[int] = 42,
) -> RawClusterLabelingViewModel:
    if clusters is None:
        clusters = [_make_cluster(), _make_cluster(), _make_cluster()]
    repo = MagicMock()
    repo.store_cluster.return_value = store_return
    physics = MagicMock()
    physics.adu_to_kev.side_effect = lambda v: v * 0.5
    def fits_info(): return (7, 2)
    return RawClusterLabelingViewModel(
        clusters=clusters,
        repository=repo,
        physics=physics,
        fits_info_provider=fits_info,
    )


# ----------------------------------------------------------------- label state


def test_default_labels_are_unclassified():
    vm = _make_vm()
    for i in range(len(vm.clusters)):
        assert vm.label_for(i) == ParticleType.UNCLASSIFIED


def test_set_label_updates_single_index():
    vm = _make_vm()
    vm.set_label(1, ParticleType.TRITIUM)
    assert vm.label_for(0) == ParticleType.UNCLASSIFIED
    assert vm.label_for(1) == ParticleType.TRITIUM
    assert vm.label_for(2) == ParticleType.UNCLASSIFIED


def test_set_all_labels_updates_every_index():
    vm = _make_vm()
    vm.set_all_labels(ParticleType.MUON)
    for i in range(len(vm.clusters)):
        assert vm.label_for(i) == ParticleType.MUON


def test_set_all_then_override_single():
    vm = _make_vm()
    vm.set_all_labels(ParticleType.TRITIUM)
    vm.set_label(1, ParticleType.GAMMA)
    assert vm.label_for(0) == ParticleType.TRITIUM
    assert vm.label_for(1) == ParticleType.GAMMA
    assert vm.label_for(2) == ParticleType.TRITIUM


# ---------------------------------------------------------------- energy_kev


def test_energy_kev_uses_physics_manager():
    cluster = _make_cluster(energy=2000.0)
    vm = _make_vm(clusters=[cluster])
    assert vm.energy_kev(0) == pytest.approx(1000.0)
    vm._physics.adu_to_kev.assert_called_once_with(2000.0)


# --------------------------------------------------------------- submit logic


def _submit_and_wait(vm: RawClusterLabelingViewModel) -> None:
    done = threading.Event()
    vm.add_phase_changed_callback(
        lambda: done.set() if vm.phase in (Phase.DONE, Phase.ERROR) else None
    )
    vm.submit()
    done.wait(timeout=5)


def test_submit_skips_unclassified_clusters():
    clusters = [_make_cluster(top=i * 10) for i in range(3)]
    vm = _make_vm(clusters=clusters)
    vm.set_label(0, ParticleType.TRITIUM)
    vm.set_label(2, ParticleType.MUON)
    # index 1 stays UNCLASSIFIED → skipped

    _submit_and_wait(vm)

    assert vm._repository.store_cluster.call_count == 2


def test_submit_stores_correct_request_fields():
    cluster = _make_cluster(energy=3000.0, sigma_x=1.8, sigma_y=1.4,
                            pixel_count=30, top=5, left=10)
    vm = _make_vm(clusters=[cluster])
    vm.set_label(0, ParticleType.TRITIUM)

    _submit_and_wait(vm)

    req: ClusterStoreRequest = vm._repository.store_cluster.call_args[0][0]
    assert req.data is None
    assert req.classification == "TRITIUM"
    assert req.sigma_x == pytest.approx(1.8)
    assert req.sigma_y == pytest.approx(1.4)
    assert req.total_pixels == 30
    assert req.total_energy == pytest.approx(3000.0)
    assert req.fits_id == 7
    assert req.hdu_id == 2
    assert req.bounding_box == {"top": 5, "left": 10, "bottom": 10, "right": 15}


def test_submit_sets_stored_count():
    clusters = [_make_cluster(top=i * 10) for i in range(4)]
    vm = _make_vm(clusters=clusters)
    vm.set_label(0, ParticleType.TRITIUM)
    vm.set_label(1, ParticleType.MUON)
    vm.set_label(2, ParticleType.ALPHA)
    # index 3 stays UNCLASSIFIED

    _submit_and_wait(vm)

    assert vm.stored_count == 3
    assert vm.phase == Phase.DONE


def test_submit_fires_phase_callbacks_in_order():
    vm = _make_vm()
    vm.set_label(0, ParticleType.TRITIUM)
    phases_seen = []
    done = threading.Event()

    def on_change():
        phases_seen.append(vm.phase)
        if vm.phase in (Phase.DONE, Phase.ERROR):
            done.set()

    vm.add_phase_changed_callback(on_change)
    vm.submit()
    done.wait(timeout=5)

    assert phases_seen[0] == Phase.SUBMITTING
    assert phases_seen[-1] == Phase.DONE


def test_submit_handles_repository_exception():
    vm = _make_vm()
    vm._repository.store_cluster.side_effect = RuntimeError("EPS down")
    vm.set_label(0, ParticleType.TRITIUM)

    _submit_and_wait(vm)

    assert vm.phase == Phase.ERROR
    assert "EPS down" in vm.error_message


def test_submit_all_unclassified_stores_nothing():
    vm = _make_vm()
    # No labels set — all UNCLASSIFIED

    _submit_and_wait(vm)

    vm._repository.store_cluster.assert_not_called()
    assert vm.stored_count == 0
    assert vm.phase == Phase.DONE


def test_store_cluster_none_return_not_counted():
    """store_cluster returning None for all labeled clusters triggers Phase.ERROR."""
    vm = _make_vm(store_return=None)
    vm.set_label(0, ParticleType.TRITIUM)

    _submit_and_wait(vm)

    assert vm.stored_count == 0
    assert vm.phase == Phase.ERROR
    assert vm.error_message is not None


def test_partial_store_failure_is_done_not_error():
    """Partial success (some stored, some not) ends as DONE."""
    clusters = [_make_cluster(top=i * 10) for i in range(3)]
    vm = _make_vm(clusters=clusters)
    vm._repository.store_cluster.side_effect = [1, None, 3]
    for i in range(3):
        vm.set_label(i, ParticleType.TRITIUM)

    _submit_and_wait(vm)

    assert vm.phase == Phase.DONE
    assert vm.stored_count == 2


def test_build_request_data_field_is_none():
    """Pixel data is never sent to EPS — data is always None."""
    cluster = _make_cluster()
    req = RawClusterLabelingViewModel._build_request(
        cluster, hdu_id=0, fits_id=1, label=ParticleType.TRITIUM
    )
    assert req.data is None


def test_build_request_converts_numpy_fields_to_json_serializable_natives():
    """Real extractors (e.g. LBNLClassicalClusterExtractor) hand off numpy-typed sigmaX/sigmaY/energy/pixelCount and bounding-
    box corners -- _build_request's int()/float() casts are the actual fix for the numpy-TypeError bug class (issue #196).

    Pin that the casts hold for numpy input, not just native input.
    """
    cluster = ClusteredEventInfo(
        boundingBox=BoundingBox(
            top=np.int64(5), left=np.int64(10),
            bottom=np.int64(10), right=np.int64(15),
        ),
        data=np.ones((5, 5), dtype=float),
        centerX=np.int64(12), centerY=np.int64(7),
        sigmaX=np.float64(1.8), sigmaY=np.float64(1.4),
        energy=np.float64(3000.0), pixelCount=np.int64(30),
    )

    req = RawClusterLabelingViewModel._build_request(
        cluster, hdu_id=2, fits_id=7, label=ParticleType.TRITIUM
    )
    d = req.to_eps_dict()
    json.dumps(d)

    assert isinstance(d["sigmaX"], float) and not isinstance(d["sigmaX"], np.floating)
    assert isinstance(d["sigmaY"], float) and not isinstance(d["sigmaY"], np.floating)
    assert isinstance(d["total_energy"], float) and not isinstance(d["total_energy"], np.floating)
    assert isinstance(d["total_pixels"], int) and not isinstance(d["total_pixels"], np.integer)
    for val in d["bounding_box"].values():
        assert isinstance(val, int) and not isinstance(val, np.integer)


def test_has_any_label_false_when_all_unclassified():
    vm = _make_vm()
    assert vm.has_any_label is False


def test_has_any_label_true_after_setting_one_label():
    vm = _make_vm()
    vm.set_label(0, ParticleType.TRITIUM)
    assert vm.has_any_label is True


def test_has_any_label_false_after_resetting_to_unclassified():
    vm = _make_vm()
    vm.set_label(0, ParticleType.TRITIUM)
    vm.set_label(0, ParticleType.UNCLASSIFIED)
    assert vm.has_any_label is False
