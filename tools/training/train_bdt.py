"""Trains the BDT tritium classifier and saves it for LBNLTritiumClassifierService.

``mlccd_models`` ships no boosted-tree model at all (only ``CCDData.x_train_bdt``
as a feature-prep helper for a BDT that would live outside the package) — the
lab's actual BDT training code isn't in this dependency. This trains a plain
``sklearn.ensemble.GradientBoostingClassifier`` from scratch as a stand-in,
using the same three features ``CCDData.x_train_bdt`` already selects
(``clusterEnergy``, ``clusterSigmaX``, ``clusterSigmaY``) — which are also
exactly the fields already present on ``ClassificationRequestCluster``
(``total_energy``, ``sigmaX``, ``sigmaY``), so ``classify_bdt()`` needs no
pixel math at inference time, just those three numbers per cluster.

Usage::

    uv run python tools/training/train_bdt.py \\
        --dataset ~/Downloads/10x10_clusters_fermilab_bkg_and_tritium/\\
fermilab_upnoised_quadrant_0_and_3_baseline_cut_balanced.pkl \\
        --output-dir ~/lbnlvis-models/lbnl_tritium

Output is a single ``bdt.joblib`` file under ``--output-dir``.
"""

import argparse
import os
import sys

import joblib
from sklearn.ensemble import GradientBoostingClassifier

sys.path.insert(0, os.path.dirname(__file__))
from _ccd_dataset import load_dataset  # noqa: E402

_DEFAULT_TRAIN_FRACTION = 0.7
_DEFAULT_VALIDATION_FRACTION = 0.15
_DEFAULT_TEST_FRACTION = 0.15
_DEFAULT_SEED = 42
_DEFAULT_N_ESTIMATORS = 200
_DEFAULT_MAX_DEPTH = 3
_DEFAULT_LEARNING_RATE = 0.1
_OUTPUT_FILENAME = "bdt.joblib"


def main() -> None:
    """Parses arguments, trains the BDT, and saves it to --output-dir/bdt.joblib."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Path to a training .pkl/.pickle file")
    parser.add_argument("--output-dir", required=True, help="Directory to write bdt.joblib into")
    parser.add_argument("--n-estimators", type=int, default=_DEFAULT_N_ESTIMATORS)
    parser.add_argument("--max-depth", type=int, default=_DEFAULT_MAX_DEPTH)
    parser.add_argument("--learning-rate", type=float, default=_DEFAULT_LEARNING_RATE)
    parser.add_argument("--train-fraction", type=float, default=_DEFAULT_TRAIN_FRACTION)
    parser.add_argument("--validation-fraction", type=float, default=_DEFAULT_VALIDATION_FRACTION)
    parser.add_argument("--test-fraction", type=float, default=_DEFAULT_TEST_FRACTION)
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    args = parser.parse_args()

    ccd_data = load_dataset(
        os.path.expanduser(args.dataset),
        args.train_fraction,
        args.validation_fraction,
        args.test_fraction,
        args.seed,
    )

    model = GradientBoostingClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        random_state=args.seed,
    )
    model.fit(ccd_data.x_train_bdt, ccd_data.y_train)

    test_accuracy = model.score(ccd_data.x_test_bdt, ccd_data.y_test)
    print(f"Test accuracy: {test_accuracy:.4f} ({len(ccd_data.y_test)} held-out clusters)")

    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, _OUTPUT_FILENAME)
    joblib.dump(model, output_path)
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
