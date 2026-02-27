# Citation for Unit Tests: ParticleType enum traits and classify_particle utility logic
# Date: 26/02/2026
# Adapted from Claude Code:
# Write unit tests for ParticleType enum and the classify_particle utility testing edge cases and classification thresholds.

"""Tests for ParticleType enum and classify_particle utility."""
import numpy as np
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.ParticleType import (
    CLASSIFICATION_THRESHOLD,
    ParticleType,
    classify_particle,
)


def _make_cluster(cnn: float, nrg: float, bdt: float) -> Cluster:
    """Creates a minimal Cluster with given classification scores."""
    return Cluster(
        boundingBox=BoundingBox(0, 0, 5, 5),
        data=np.ones((5, 5)),
        centerX=2,
        centerY=2,
        cnnClassification=cnn,
        nrgClassification=nrg,
        bdtClassification=bdt,
    )


# --- ParticleType enum ---

def test_all_members_have_attributes():
    """Every ParticleType should have display_name, symbol, color."""
    for pt in ParticleType:
        assert isinstance(pt.display_name, str)
        assert isinstance(pt.symbol, str)
        assert isinstance(pt.badge_color, str)
        assert pt.badge_color.startswith("#")


def test_tritium_symbol():
    """Tritium should use the Unicode superscript-3 H symbol."""
    assert ParticleType.TRITIUM.symbol == "\u00b3H"


def test_compton_symbol():
    """Compton electron should use e with superscript minus."""
    assert ParticleType.COMPTON.symbol == "e\u207b"


def test_gamma_symbol():
    """Gamma should use the Greek lowercase gamma."""
    assert ParticleType.GAMMA.symbol == "\u03b3"


def test_muon_symbol():
    """Muon should use the Greek lowercase mu."""
    assert ParticleType.MUON.symbol == "\u03bc"


def test_alpha_symbol():
    """Alpha should use the Greek lowercase alpha."""
    assert ParticleType.ALPHA.symbol == "\u03b1"


def test_unclassified_symbol():
    """Unclassified should use a question mark."""
    assert ParticleType.UNCLASSIFIED.symbol == "?"


# --- classify_particle ---

def test_high_confidence_returns_tritium():
    """Scores above threshold should classify as Tritium."""
    cluster = _make_cluster(0.90, 0.85, 0.80)
    pt, score = classify_particle(cluster)
    assert pt == ParticleType.TRITIUM
    assert score == 0.90


def test_low_confidence_returns_unclassified():
    """Scores below threshold should classify as Unclassified."""
    cluster = _make_cluster(0.30, 0.25, 0.20)
    pt, score = classify_particle(cluster)
    assert pt == ParticleType.UNCLASSIFIED
    assert score == 0.30


def test_threshold_boundary():
    """Exactly at threshold should classify as Tritium."""
    cluster = _make_cluster(
        CLASSIFICATION_THRESHOLD, 0.0, 0.0
    )
    pt, _ = classify_particle(cluster)
    assert pt == ParticleType.TRITIUM


def test_just_below_threshold():
    """Just below threshold should be Unclassified."""
    cluster = _make_cluster(
        CLASSIFICATION_THRESHOLD - 0.01, 0.0, 0.0
    )
    pt, _ = classify_particle(cluster)
    assert pt == ParticleType.UNCLASSIFIED


def test_best_score_across_models():
    """Should pick the max score across all three models."""
    cluster = _make_cluster(0.50, 0.80, 0.60)
    pt, score = classify_particle(cluster)
    assert pt == ParticleType.TRITIUM
    assert score == 0.80


def test_all_zero_scores():
    """Zero scores should be Unclassified with score 0."""
    cluster = _make_cluster(0.0, 0.0, 0.0)
    pt, score = classify_particle(cluster)
    assert pt == ParticleType.UNCLASSIFIED
    assert score == 0.0


# --- classify_particle with custom threshold ---

def test_custom_threshold_lower():
    """A lower threshold should classify more events as Tritium."""
    cluster = _make_cluster(0.50, 0.40, 0.30)
    pt, score = classify_particle(cluster, threshold=0.50)
    assert pt == ParticleType.TRITIUM
    assert score == 0.50


def test_custom_threshold_higher():
    """A higher threshold should classify fewer events as Tritium."""
    cluster = _make_cluster(0.80, 0.70, 0.60)
    pt, score = classify_particle(cluster, threshold=0.90)
    assert pt == ParticleType.UNCLASSIFIED
    assert score == 0.80


def test_custom_threshold_boundary():
    """Score exactly at custom threshold should classify as Tritium."""
    cluster = _make_cluster(0.60, 0.0, 0.0)
    pt, _ = classify_particle(cluster, threshold=0.60)
    assert pt == ParticleType.TRITIUM


def test_custom_threshold_just_below():
    """Score just below custom threshold should be Unclassified."""
    cluster = _make_cluster(0.59, 0.0, 0.0)
    pt, _ = classify_particle(cluster, threshold=0.60)
    assert pt == ParticleType.UNCLASSIFIED
