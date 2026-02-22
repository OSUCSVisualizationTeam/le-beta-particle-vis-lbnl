# Citation for Unit Tests: Tests for ClusterExtractorFactory ensuring correct implementation selection.
# Date: 21/02/2026
# Adapted from Claude Code:
# Analyze the ClusterExtractor logic and implementations, derive suitable test cases to cover the most relevant scenarios

"""Tests for ClusterExtractorFactory."""

from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.ClusterExtractorFactory import (
    create_cluster_extractor,
)
from le_beta_vis.common.GeneralClusterExtractor import (
    GeneralClusterExtractor,
)
from le_beta_vis.common.LBNLClassicalClusterExtractor import (
    LBNLClassicalClusterExtractor,
)
from le_beta_vis.common.LBNLOptimizedClusterExtractor import (
    LBNLOptimizedClusterExtractor,
)
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor


def _config_with_method(method: str) -> MockConfigurationService:
    config = MockConfigurationService()
    config.set("gui:raw_analysis:cluster_extractor_method", method)
    return config


class TestClusterExtractorFactory:
    def test_default_returns_lbnl_classical(self):
        config = MockConfigurationService()
        # Default in MockConfigurationService doesn't have this key,
        # so factory uses its own default "lbnl_classical"
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, LBNLClassicalClusterExtractor)

    def test_mock_method_returns_mock(self):
        config = _config_with_method("mock")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, MockClusterExtractor)

    def test_general_method_returns_general(self):
        config = _config_with_method("general")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, GeneralClusterExtractor)

    def test_optimized_method_returns_optimized(self):
        config = _config_with_method("lbnl_optimized")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, LBNLOptimizedClusterExtractor)

    def test_unknown_method_falls_back_to_lbnl(self):
        config = _config_with_method("nonexistent_algorithm")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, LBNLClassicalClusterExtractor)

