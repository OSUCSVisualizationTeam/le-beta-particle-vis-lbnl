# Citation for Unit Tests: HistoricalViewModel properties
# Date: 26/02/2026
# Adapted from Claude Code:
# Write pure Python unit tests for HistoricalViewModel checking
# configuration-driven properties.

from unittest.mock import MagicMock
from le_beta_vis.frontend.viewmodels.HistoricalViewModel import (
    HistoricalViewModel,
)
from mock_configuration_service import MockConfigurationService
from le_beta_vis.common.MockEventRepository import (
    MockEventRepository,
)
from MockThumbnailLoaderService import MockThumbnailLoaderService


def _make_physics_mock():
    mock = MagicMock()
    mock.kev_conversion_factor = 1.02857e-5
    return mock


def test_classification_threshold_default():
    """classificationThreshold should default to 0.75."""
    config = MockConfigurationService()
    vm = HistoricalViewModel(
        config, _make_physics_mock(), MockEventRepository(),
        MockThumbnailLoaderService(),
    )
    assert vm.classificationThreshold == 0.75
