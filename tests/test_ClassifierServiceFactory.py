"""Tests for ClassifierServiceFactory.create_classifier_service (issue #54)."""

from le_beta_vis.common.ClassifierServiceFactory import create_classifier_service
from le_beta_vis.common.LBNLTritiumClassifierService import LBNLTritiumClassifierService
from le_beta_vis.common.MockClassifierService import MockClassifierService


class _FakeConfig:
    def __init__(self, backend="mock"):
        self._backend = backend

    def get(self, key, default=None):
        if key == "classifier:service_backend":
            return self._backend
        if key == "classifier:lbnl_model_weights_dir":
            return "/nonexistent/weights/dir"
        return default

    def get_int(self, key, default, minimum=None, maximum=None):
        return default


def test_default_backend_is_mock():
    service = create_classifier_service(_FakeConfig(backend="mock"))
    assert isinstance(service, MockClassifierService)


def test_lbnl_tritium_backend_returns_real_service():
    service = create_classifier_service(_FakeConfig(backend="lbnl_tritium"))
    assert isinstance(service, LBNLTritiumClassifierService)


def test_unknown_backend_falls_back_to_mock(caplog):
    service = create_classifier_service(_FakeConfig(backend="not_a_real_backend"))
    assert isinstance(service, MockClassifierService)
    assert "Unknown classifier service backend" in caplog.text
