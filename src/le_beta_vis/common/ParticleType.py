from enum import Enum
from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .Cluster import Cluster

# Threshold above which the highest model confidence
# is considered a positive classification.
CLASSIFICATION_THRESHOLD = 0.75


class ParticleType(Enum):
    """Known particle types with display metadata.

    Each member carries ``(display_name, symbol, badge_color)``.
    The symbol uses actual Unicode characters (per project
    convention) for direct use in QLabel text.
    """

    TRITIUM = ("Tritium", "\u00b3H", "#2ecc71")
    MUON = ("Muon", "\u03bc", "#3498db")
    COMPTON = ("Compton Electron", "e\u207b", "#e67e22")
    GAMMA = ("Gamma", "\u03b3", "#9b59b6")
    ALPHA = ("Alpha", "\u03b1", "#e74c3c")
    UNCLASSIFIED = ("Unknown", "?", "#95a5a6")

    def __init__(
        self, display_name: str, symbol: str, badge_color: str
    ) -> None:
        self.display_name = display_name
        self.symbol = symbol
        self.badge_color = badge_color


def classify_particle(
    cluster: "Cluster",
    threshold: float = CLASSIFICATION_THRESHOLD,
) -> Tuple[ParticleType, float]:
    """Derives a particle type and confidence from classification scores.

    Currently the ML pipeline produces only tritium confidence
    scores (CNN, NRG, BDT).  The highest score across the three
    models is compared against the given *threshold*.

    When the backend adds multi-class models, update this function
    — the rest of the UI consumes ``ParticleType`` and stays stable.

    Args:
        cluster: A Cluster with classification scores.
        threshold: Minimum confidence for positive classification.
            Defaults to ``CLASSIFICATION_THRESHOLD``.

    Returns:
        A tuple of ``(ParticleType, confidence)`` where confidence
        is the best score across all models (0.0–1.0).
    """
    best_score = max(
        cluster.cnnClassification,
        cluster.nrgClassification,
        cluster.bdtClassification,
    )
    if best_score >= threshold:
        return ParticleType.TRITIUM, best_score
    return ParticleType.UNCLASSIFIED, best_score
