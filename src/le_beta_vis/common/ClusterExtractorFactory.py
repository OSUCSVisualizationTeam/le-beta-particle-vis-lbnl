import logging
from enum import Enum

from .ClusterExtractor import ClusterExtractor
from .ConfigurationService import ConfigurationService
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
    sigma: float = config.get(
        "gui:raw_analysis:clustering_threshold", 4.0
    )
    ped_width: int = config.get(
        "global:physics:ped_width", 1400
    )
    kev: float = config.get(
        "global:physics:kev_conversion", 1.02857e-5
    )

    try:
        method = ClusterExtractorMethod(method_str)
    except ValueError:
        logger.warning(
            "Unknown cluster extractor method '%s', "
            "falling back to lbnl_classical",
            method_str,
        )
        method = ClusterExtractorMethod.LBNL_CLASSICAL

    if method == ClusterExtractorMethod.MOCK:
        return MockClusterExtractor()

    if method == ClusterExtractorMethod.LBNL_OPTIMIZED:
        return LBNLOptimizedClusterExtractor(
            sigma_multiplier=sigma,
            ped_width=ped_width,
            kev_conversion=kev,
        )

    if method == ClusterExtractorMethod.GENERAL:
        return GeneralClusterExtractor(
            sigma_multiplier=sigma,
            ped_width=ped_width,
            kev_conversion=kev,
        )

    # Default: LBNL_CLASSICAL
    return LBNLClassicalClusterExtractor(
        sigma_multiplier=sigma,
        ped_width=ped_width,
        kev_conversion=kev,
    )
