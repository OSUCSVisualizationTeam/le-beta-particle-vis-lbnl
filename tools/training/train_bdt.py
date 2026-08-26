"""Trains the BDT tritium classifier and saves it for LBNLTritiumClassifierService.

NOT a reproduction of a lab model: ``mlccd_models`` has no boosted-tree
implementation at all, so this trains a plain
``sklearn.ensemble.GradientBoostingClassifier`` from scratch on
``[clusterEnergy, clusterSigmaX, clusterSigmaY]`` as a stand-in. Output is a
single ``bdt.joblib`` file under ``--output-dir``. See
``tools/training/README.md`` for usage and rationale.
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
_DEFAULT_N_ESTIMATORS = 500
_DEFAULT_MAX_DEPTH = 3
_DEFAULT_LEARNING_RATE = 0.05
_DEFAULT_N_ITER_NO_CHANGE = 20
_OUTPUT_FILENAME = "bdt.joblib"


def main() -> None:
    """Parses arguments, trains the BDT, and saves it to --output-dir/bdt.joblib."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Path to a training .pkl/.pickle file")
    parser.add_argument("--output-dir", required=True, help="Directory to write bdt.joblib into")
    parser.add_argument("--n-estimators", type=int, default=_DEFAULT_N_ESTIMATORS)
    parser.add_argument("--max-depth", type=int, default=_DEFAULT_MAX_DEPTH)
    parser.add_argument("--learning-rate", type=float, default=_DEFAULT_LEARNING_RATE)
    parser.add_argument("--n-iter-no-change", type=int, default=_DEFAULT_N_ITER_NO_CHANGE)
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
        n_iter_no_change=args.n_iter_no_change,
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
