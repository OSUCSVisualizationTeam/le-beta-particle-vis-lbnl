"""Trains the NRG (energy-flow) tritium classifier and saves it for LBNLTritiumClassifierService.

Wraps ``mlccd_models.PFNModel`` (an energyflow Particle Flow Network over a
per-pixel energy+position point cloud, via ``GetPixelClusterData``) as-is,
training it against one of the Fermilab background / tritium datasets shared
by Dr. Rofors.

Usage::

    uv run python tools/training/train_nrg.py \\
        --dataset ~/Downloads/10x10_clusters_fermilab_bkg_and_tritium/\\
fermilab_upnoised_quadrant_0_and_3_baseline_cut_balanced.pkl \\
        --output-dir ~/lbnlvis-models/lbnl_tritium

Output is ``nrg.weights.h5`` plus a ``nrg.meta.json`` sidecar recording the
exact preprocessing/architecture parameters used (``normalize_threshold_low``,
``normalize_threshold_high``, ``threshold``, ``pixels_around_brightest_pixel``,
``input_dim``, ``phi_sizes``, ``f_sizes``). ``classify_nrg()`` must reconstruct
the identical preprocessing + ``GetPixelClusterData`` call + ``PFNModel``
architecture before calling ``load_weights()`` — a runtime config key would
silently drift from whatever a given weights file was actually trained with,
so the sidecar (shipped alongside the weights) is the single source of truth
instead.

Raw cluster pixel values are keV, ranging up to ~1e6 for hot outlier pixels.
``mlccd_models.GetPixelClusterData`` (lab code, used as-is) hardcodes
``np.clip(intensity, 0, 2.0)`` on whatever pixel values it's given — with raw
keV inputs, 99.9%+ of real in-cluster pixels blow past that ceiling and
collapse to the same clipped value, destroying the intensity signal (measured
directly: NRG stuck at ~51% test accuracy, chance level, with raw keV
inputs). Same root cause the CNN script already handles via
``CCDData.normalize()`` — NRG just never had that step. ``--normalize-percentile``
clips at that percentile of the training set's pixel distribution and
rescales to [0, 1] via ``CCDData.normalize()`` *before* ``prepare_energyflow_format()``,
so real signal pixels land inside ``GetPixelClusterData``'s clip range instead
of all collapsing to it.

``--energy-threshold-kev`` (still expressed in raw keV on the CLI, for the
same "4 sigma" Fermilab-noise-level convention used elsewhere in this
project) is rescaled by the same ``normalize_threshold_high`` before being
passed to ``GetPixelClusterData`` as ``threshold`` — that function compares
its ``threshold`` argument against whatever pixel values it's actually given,
which are the *normalized* ones once ``ccd_data.normalize()`` has run.
"""

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from _ccd_dataset import load_dataset  # noqa: E402

import mlccd_diffusion  # noqa: E402
import mlccd_models  # noqa: E402

_DEFAULT_TRAIN_FRACTION = 0.7
_DEFAULT_VALIDATION_FRACTION = 0.15
_DEFAULT_TEST_FRACTION = 0.15
_DEFAULT_SEED = 42
_DEFAULT_EPOCHS = 20
_DEFAULT_BATCH_SIZE = 128
_DEFAULT_PIXELS_AROUND_BRIGHTEST_PIXEL = 50
_DEFAULT_PHI_SIZES = (100, 100, 128)
_DEFAULT_F_SIZES = (100, 100, 100)
_DEFAULT_NORMALIZE_PERCENTILE = 99.9
_WEIGHTS_FILENAME = "nrg.weights.h5"
_META_FILENAME = "nrg.meta.json"


def _parse_int_tuple(value: str) -> tuple:
    return tuple(int(v) for v in value.split(","))


def main() -> None:
    """Parses arguments, trains the NRG (PFN) model, and saves weights + a meta sidecar."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Path to a training .pkl/.pickle file")
    parser.add_argument("--output-dir", required=True, help="Directory to write nrg.weights.h5 + nrg.meta.json into")
    parser.add_argument("--epochs", type=int, default=_DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=_DEFAULT_BATCH_SIZE)
    parser.add_argument("--train-fraction", type=float, default=_DEFAULT_TRAIN_FRACTION)
    parser.add_argument("--validation-fraction", type=float, default=_DEFAULT_VALIDATION_FRACTION)
    parser.add_argument("--test-fraction", type=float, default=_DEFAULT_TEST_FRACTION)
    parser.add_argument("--seed", type=int, default=_DEFAULT_SEED)
    parser.add_argument(
        "--energy-threshold-kev",
        type=float,
        default=None,
        help="Pixel intensity floor below which pixels are ignored (default: 4x Fermilab noise level)",
    )
    parser.add_argument(
        "--pixels-around-brightest-pixel",
        type=int,
        default=_DEFAULT_PIXELS_AROUND_BRIGHTEST_PIXEL,
    )
    parser.add_argument("--phi-sizes", type=_parse_int_tuple, default=_DEFAULT_PHI_SIZES)
    parser.add_argument("--f-sizes", type=_parse_int_tuple, default=_DEFAULT_F_SIZES)
    parser.add_argument(
        "--normalize-percentile",
        type=float,
        default=_DEFAULT_NORMALIZE_PERCENTILE,
        help="Percentile of training pixel values used as the normalize() clip ceiling",
    )
    args = parser.parse_args()

    threshold_kev = args.energy_threshold_kev
    if threshold_kev is None:
        threshold_kev = 4 * mlccd_diffusion.fermilab_noise_level(unit="keV")

    ccd_data = load_dataset(
        os.path.expanduser(args.dataset),
        args.train_fraction,
        args.validation_fraction,
        args.test_fraction,
        args.seed,
    )

    normalize_threshold_high = float(np.percentile(ccd_data.images, args.normalize_percentile))
    print(f"Normalizing pixels to [0, 1] with threshold_high={normalize_threshold_high:.2f} keV")
    ccd_data.normalize(threshold_low=0.0, threshold_high=normalize_threshold_high)

    # GetPixelClusterData compares its threshold against whatever pixel values it's given —
    # now the normalized ones — so the raw-keV threshold must be rescaled the same way.
    normalized_threshold = threshold_kev / normalize_threshold_high
    print(
        f"Preparing energyflow point clouds with threshold={normalized_threshold:.2e} "
        f"(normalized; {threshold_kev:.4f} keV raw)"
    )
    ccd_data.prepare_energyflow_format(
        threshold=normalized_threshold,
        pixels_around_brightest_pixel=args.pixels_around_brightest_pixel,
    )

    model = mlccd_models.PFNModel(
        input_dim=3,
        Phi_sizes=args.phi_sizes,
        F_sizes=args.f_sizes,
        output_dim=1,
    )
    model.fit(ccd_data, epochs=args.epochs, batch_size=args.batch_size)

    test_predictions = (model.predict(ccd_data.x_test_energyflow).ravel() >= 0.5).astype(int)
    test_accuracy = float(np.mean(test_predictions == ccd_data.y_test))
    print(f"Test accuracy: {test_accuracy:.4f} ({len(ccd_data.y_test)} held-out clusters)")

    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    weights_path = os.path.join(output_dir, _WEIGHTS_FILENAME)
    model.model.save_weights(weights_path)
    print(f"Saved {weights_path}")

    meta_path = os.path.join(output_dir, _META_FILENAME)
    with open(meta_path, "w") as f:
        json.dump(
            {
                "normalize_threshold_low": 0.0,
                "normalize_threshold_high": normalize_threshold_high,
                "threshold": normalized_threshold,
                "pixels_around_brightest_pixel": args.pixels_around_brightest_pixel,
                "input_dim": 3,
                "phi_sizes": list(args.phi_sizes),
                "f_sizes": list(args.f_sizes),
            },
            f,
            indent=2,
        )
    print(f"Saved {meta_path}")


if __name__ == "__main__":
    main()
