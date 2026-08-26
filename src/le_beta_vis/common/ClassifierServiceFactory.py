import logging
from enum import Enum

from .ClassifierService import ClassifierService
from .ConfigurationService import ConfigurationService
from .LBNLTritiumClassifierService import LBNLTritiumClassifierService
from .MockClassifierService import MockClassifierService

logger = logging.getLogger(__name__)


class ClassifierServiceBackend(str, Enum):
    """Supported ClassifierService backends."""

    MOCK = "mock"
    LBNL_TRITIUM = "lbnl_tritium"


def create_classifier_service(config: ConfigurationService) -> ClassifierService:
    """Create a ClassifierService from application configuration.

    Reads ``classifier:service_backend``. Falls back to the mock backend
    with a logged warning on an unrecognized value. Callers should construct
    and cache one instance (e.g. at View/PollingThread construction) rather
    than calling this per classification request — ``lbnl_tritium`` eagerly
    loads three trained models.
    """
    backend_str: str = config.get("classifier:service_backend", "mock")

    try:
        backend = ClassifierServiceBackend(backend_str)
    except ValueError:
        logger.warning(
            "Unknown classifier service backend '%s', falling back to mock",
            backend_str,
        )
        backend = ClassifierServiceBackend.MOCK

    if backend == ClassifierServiceBackend.LBNL_TRITIUM:
        return LBNLTritiumClassifierService(config)

    return MockClassifierService()
