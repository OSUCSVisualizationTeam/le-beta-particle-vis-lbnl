import logging
from enum import Enum

from .ClusterExtractor import ClusterExtractor
from .ConfigurationService import ConfigurationService
from .PhysicsConversionManager import PhysicsConversionManager
from .GeneralClusterExtractor import GeneralClusterExtractor
from .LBNLClassicalClusterExtractor import LBNLClassicalClusterExtractor
from .LBNLOptimizedClusterExtractor import LBNLOptimizedClusterExtractor
from .MockClusterExtractor import MockClusterExtractor

logger = logging.getLogger(__name__)


class ClusterExtractorMethod(str, Enum):
    """Supported cluster extraction backends."""

    MOCK = "mock"
    LBNL_CLASSICAL = "lbnl_classical"
    LBNL_OPTIMIZED = "lbnl_optimized"
    GENERAL = "general"


def create_cluster_extractor(
    config: ConfigurationService,
    physics_manager: PhysicsConversionManager,
) -> ClusterExtractor:
    """Create a ClusterExtractor from application configuration.

    The ``general`` backend is a domain-agnostic multi-cluster
    extractor suitable for any ROI analysis.  The ``lbnl_classical``
    and ``lbnl_optimized`` backends are tritium-detection specific
    and depend on the lab's ``mlccd_diffusion`` classification
    pipeline.

    Reads the following config keys:
    - ``gui:raw_analysis:cluster_extractor_method`` (str)
    - ``gui:raw_analysis:clustering_threshold`` (float)
    - ``global:physics:ped_width`` (int)
    - ``global:physics:kev_conversion`` (float)
    """
    method_str: str = config.get(
        "gui:raw_analysis:cluster_extractor_method",
        "lbnl_classical",
    )
    sigma: float = config.get("gui:raw_analysis:clustering_threshold", 4.0)

    try:
        method = ClusterExtractorMethod(method_str)
    except ValueError:
        logger.warning(
            "Unknown cluster extractor method '%s', " "falling back to lbnl_classical",
            method_str,
        )
        method = ClusterExtractorMethod.LBNL_CLASSICAL

    if method == ClusterExtractorMethod.MOCK:
        return MockClusterExtractor()

    if method == ClusterExtractorMethod.LBNL_OPTIMIZED:
        return LBNLOptimizedClusterExtractor(
            physics_manager=physics_manager,
            sigma_multiplier=sigma,
        )

    if method == ClusterExtractorMethod.GENERAL:
        return GeneralClusterExtractor(
            physics_manager=physics_manager,
            sigma_multiplier=sigma,
        )

    # Default: LBNL_CLASSICAL
    return LBNLClassicalClusterExtractor(
        physics_manager=physics_manager,
        sigma_multiplier=sigma,
    )
