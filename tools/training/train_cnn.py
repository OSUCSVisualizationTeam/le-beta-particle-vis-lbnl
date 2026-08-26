"""Trains the CNN tritium classifier and saves it for LBNLTritiumClassifierService.

Wraps ``mlccd_models.CNNModel`` as-is against a Fermilab background/tritium dataset. Output is ``cnn.keras`` plus a
``cnn.meta.json`` sidecar under ``--output-dir``. See ``tools/training/README.md`` for usage and rationale (pixel
normalization, class balancing, the ``*.meta.json`` contract).
"""

import argparse
import json
import os
import sys

import numpy as np
import tensorflow as tf
import wandb

sys.path.insert(0, os.path.dirname(__file__))
from _ccd_dataset import load_dataset  # noqa: E402

import mlccd_models  # noqa: E402

_DEFAULT_TRAIN_FRACTION = 0.7
_DEFAULT_VALIDATION_FRACTION = 0.15
_DEFAULT_TEST_FRACTION = 0.15
_DEFAULT_SEED = 42
_DEFAULT_EPOCHS = 20
_DEFAULT_BATCH_SIZE = 64
_DEFAULT_LEARNING_RATE = 1e-3
_DEFAULT_NORMALIZE_PERCENTILE = 99.9
_OUTPUT_FILENAME = "cnn.keras"
_META_FILENAME = "cnn.meta.json"


def main() -> None:
    """Parses arguments, trains the CNN, and saves it to --output-dir/cnn.keras."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", required=True, help="Path to a training .pkl/.pickle file"
    )
    parser.add_argument(
        "--output-dir", required=True, help="Directory to write cnn.keras into"
    )
    parser.add_argument("--epochs", type=int, default=_DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=_DEFAULT_BATCH_SIZE)
    parser.add_argument("--learning-rate", type=float, default=_DEFAULT_LEARNING_RATE)
    parser.add_argument("--train-fraction", type=float, default=_DEFAULT_TRAIN_FRACTION)
    parser.add_argument(
        "--validation-fraction", type=float, default=_DEFAULT_VALIDATION_FRACTION
    )
    parser.add_argument("--test-fraction", type=float, default=_DEFAULT_TEST_FRACTION)
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    parser.add_argument(
        "--normalize-percentile",
        type=float,
        default=_DEFAULT_NORMALIZE_PERCENTILE,
        help="Percentile of training pixel values used as the normalize() clip ceiling",
    )
    args = parser.parse_args()

    ccd_data = load_dataset(
        os.path.expanduser(args.dataset),
        args.train_fraction,
        args.validation_fraction,
        args.test_fraction,
        args.seed,
    )
    wandb.init(
        # Set the wandb entity where your project will be logged (generally your team name).
        entity="juanguerrero-osu-oregon-state-university",
        # Set the wandb project where this run will be logged.
        project="lbnlvis",
        # Track hyperparameters and run metadata.
        config={
            "architecture": "CNN",
            "dataset": args.dataset,
            "epochs": args.epochs,
        },
    )
    threshold_high = float(np.percentile(ccd_data.images, args.normalize_percentile))
    print(f"Normalizing pixels to [0, 1] with threshold_high={threshold_high:.2f} keV")
    ccd_data.normalize(threshold_low=0.0, threshold_high=threshold_high)

    model = mlccd_models.CNNModel(
        ccd_data.IMAGE_WIDTH, ccd_data.IMAGE_HEIGHT, ccd_data.IMAGE_CHANNELS
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=args.learning_rate),
        loss=tf.keras.losses.BinaryFocalCrossentropy(apply_class_balancing=True),
    )

    mlccd_models.train(
        model=model,
        ccd_data=ccd_data,
        config={"epochs": args.epochs, "batch_size": args.batch_size},
        offline=True,
    )

    test_predictions = (model.predict(ccd_data.x_test).ravel() >= 0.5).astype(int)
    test_accuracy = float(np.mean(test_predictions == ccd_data.y_test))
    print(
        f"Test accuracy: {test_accuracy:.4f} ({len(ccd_data.y_test)} held-out clusters)"
    )

    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, _OUTPUT_FILENAME)
    model.save(output_path)
    print(f"Saved {output_path}")
    wandb.save(output_path)

    meta_path = os.path.join(output_dir, _META_FILENAME)
    with open(meta_path, "w") as f:
        json.dump(
            {
                "normalize_threshold_low": 0.0,
                "normalize_threshold_high": threshold_high,
            },
            f,
            indent=2,
        )
    wandb.save(meta_path)
    print(f"Saved {meta_path}")


if __name__ == "__main__":
    main()
