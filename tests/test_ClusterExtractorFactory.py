"""Tests for ClusterExtractorFactory."""

from le_beta_vis.common.ConfigurationService import MockConfigurationService
from le_beta_vis.common.ClusterExtractorFactory import (
    create_cluster_extractor,
)
from le_beta_vis.common.LBNLClassicalClusterExtractor import (
    LBNLClassicalClusterExtractor,
)
from le_beta_vis.common.LBNLOptimizedClusterExtractor import (
    LBNLOptimizedClusterExtractor,
)
from le_beta_vis.common.MockClusterExtractor import MockClusterExtractor
from le_beta_vis.common.OptimalClassicalClusterExtractor import (
    OptimalClassicalClusterExtractor,
)


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

    def test_optimal_method_returns_optimal(self):
        config = _config_with_method("optimal_classical")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, OptimalClassicalClusterExtractor)

    def test_optimized_method_returns_optimized(self):
        config = _config_with_method("lbnl_optimized")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, LBNLOptimizedClusterExtractor)

    def test_unknown_method_falls_back_to_lbnl(self):
        config = _config_with_method("nonexistent_algorithm")
        extractor = create_cluster_extractor(config)
        assert isinstance(extractor, LBNLClassicalClusterExtractor)
