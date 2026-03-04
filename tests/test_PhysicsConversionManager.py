import numpy as np
import pytest
from typing import Union
from le_beta_vis.common import PhysicsConversionManager, PhysicsConversionManagerImpl


class MockConfig:
    """Simple mock for ConfigurationService."""

    def __init__(self, data=None):
        self.data = data or {}

    def get(self, key, default=None):
        return self.data.get(key, default)


def test_conversion_factor_retrieval():
    """Verify that the implementation fetches the factor from config."""
    mock_config = MockConfig({"global:physics:kev_conversion": 0.5})
    manager = PhysicsConversionManagerImpl(mock_config)

    assert manager.kev_conversion_factor == 0.5


def test_pedestal_width_retrieval():
    """Verify that the implementation fetches pedestal width from config."""
    mock_config = MockConfig({"global:physics:ped_width": 100})
    manager = PhysicsConversionManagerImpl(mock_config)

    assert manager.pedestal_width == 100


def test_calculate_threshold():
    """Verify threshold calculation."""
    mock_config = MockConfig({"global:physics:ped_width": 100})
    manager = PhysicsConversionManagerImpl(mock_config)

    # 4.0 * 100 = 400.0
    assert manager.calculate_threshold(4.0) == 400.0


def test_adu_to_kev_scalar():
    """Verify scalar conversion logic."""
    mock_config = MockConfig({"global:physics:kev_conversion": 0.1})
    manager = PhysicsConversionManagerImpl(mock_config)

    # 100 ADU * 0.1 keV/ADU = 10 keV
    assert manager.adu_to_kev(100.0) == pytest.approx(10.0)


def test_adu_to_kev_array():
    """Verify array conversion logic (NumPy)."""
    mock_config = MockConfig({"global:physics:kev_conversion": 0.1})
    manager = PhysicsConversionManagerImpl(mock_config)

    data = np.array([100.0, 200.0, 300.0])
    expected = np.array([10.0, 20.0, 30.0])

    result = manager.adu_to_kev(data)
    np.testing.assert_allclose(result, expected)


def test_default_fallback():
    """Verify fallback to the hardcoded physics constant."""
    # Empty config that returns defaults
    mock_config = MockConfig({})  # Empty dict, so get() returns default
    manager = PhysicsConversionManagerImpl(mock_config)

    # Default is 1.02857e-5
    expected_default_kev = 1.02857e-5
    # Default ped_width is 1400
    expected_default_ped = 1400

    assert manager.kev_conversion_factor == pytest.approx(expected_default_kev)
    assert manager.pedestal_width == expected_default_ped
    assert manager.calculate_threshold(4.0) == 4.0 * expected_default_ped


class MockPhysicsManager(PhysicsConversionManager):
    """A mock implementation of the PhysicsConversionManager interface."""

    def __init__(self, factor: float, ped_width: int):
        self._factor = factor
        self._ped_width = ped_width

    @property
    def kev_conversion_factor(self) -> float:
        return self._factor

    @property
    def pedestal_width(self) -> int:
        return self._ped_width

    def calculate_threshold(self, sigma: float) -> float:
        return sigma * self._ped_width

    def adu_to_kev(self, value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        return value * self._factor


def test_mock_implementation():
    """Verify that we can mock the interface directly."""
    # This demonstrates the benefit of the interface-based design
    mock_manager = MockPhysicsManager(factor=2.0, ped_width=50)

    assert mock_manager.kev_conversion_factor == 2.0
    assert mock_manager.pedestal_width == 50
    assert mock_manager.calculate_threshold(3.0) == 150.0
    assert mock_manager.adu_to_kev(10.0) == 20.0
