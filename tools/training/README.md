# Training the LBNL Tritium Classifiers

Three standalone scripts train the CNN, NRG, and BDT models consumed by
`LBNLTritiumClassifierService`, plus a shared dataset-loading helper
(`_ccd_dataset.py`). Each trainer writes its artifacts to `--output-dir`, which
is what `classifier:lbnl_model_weights_dir` should point at.

All three train against one of the Fermilab background/tritium datasets shared
by Dr. Rofors — `.pkl` files matching `mlccd_models.CCDData.read_pkl()`'s
schema.

## train_cnn.py

Wraps `mlccd_models.CNNModel` (a raw-pixel Keras CNN over the 10x10 cluster
image) as-is. Output is `cnn.keras` plus a `cnn.meta.json` sidecar.

```bash
uv run python tools/training/train_cnn.py \
    --dataset ~/Downloads/10x10_clusters_fermilab_bkg_and_tritium/\
fermilab_upnoised_quadrant_0_and_3_baseline_cut_unbalanced.pkl \
    --output-dir ~/lbnlvis-models/lbnl_tritium
```

**Pixel normalization.** Raw cluster pixel values are keV, ranging up to ~1e6
for hot outlier pixels (the same outlier-domination problem documented for
thumbnail colormap scaling). Fed directly into the CNN, this produces
enormous unstable binary-crossentropy loss (~1200 in early testing).
`--normalize-percentile` clips at that percentile of the training set's pixel
distribution and rescales to [0, 1] via `CCDData.normalize()` before
training, which brought the same run's loss down to ~0.34 and falling. The
same `threshold_high` must be reapplied at inference time — a runtime config
key would silently drift from whatever a given weights file was actually
trained with, so (mirroring the NRG trainer's `nrg.meta.json`) the exact
value used here is written to `cnn.meta.json` and `classify_cnn()` reads it
from there.

**Class balancing.** Trains against the `_unbalanced` dataset variant
(natural class prior, tritium is rare) rather than the `_balanced` one: the
lab's own `tritium_recognition_cnn.ipynb` does the same and corrects for the
imbalance inside the loss instead of resampling the data, via
`BinaryFocalCrossentropy(apply_class_balancing=True)` — matched in this
script. A model trained on an artificially resampled 50/50 dataset with an
uncorrected loss produces probabilities calibrated to that 50/50 prior, which
is why the first version of this model badly over-triggered against real
field data where tritium events are a small minority.

## train_nrg.py

Wraps `mlccd_models.PFNModel` (an energyflow Particle Flow Network over a
per-pixel energy+position point cloud, via `GetPixelClusterData`) as-is.
Output is `nrg.weights.h5` plus a `nrg.meta.json` sidecar.

```bash
uv run python tools/training/train_nrg.py \
    --dataset ~/Downloads/10x10_clusters_fermilab_bkg_and_tritium/\
fermilab_upnoised_quadrant_0_and_3_baseline_cut_unbalanced.pkl \
    --output-dir ~/lbnlvis-models/lbnl_tritium
```

**Class balancing.** Trains against the `_unbalanced` dataset variant
(natural class prior), for the same reason as the CNN trainer. `PFNModel`'s
loss isn't swappable for a class-balancing variant the way the CNN's is, so
the correction here is `CCDData.training_class_weights()` passed through as
`class_weight` to `model.fit()` instead.

**The `nrg.meta.json` contract.** The sidecar records the exact
preprocessing/architecture parameters used (`normalize_threshold_low`,
`normalize_threshold_high`, `threshold`, `pixels_around_brightest_pixel`,
`input_dim`, `phi_sizes`, `f_sizes`). `classify_nrg()` must reconstruct the
identical preprocessing + `GetPixelClusterData` call + `PFNModel`
architecture before calling `load_weights()` — a runtime config key would
silently drift from whatever a given weights file was actually trained with,
so the sidecar (shipped alongside the weights) is the single source of truth
instead.

**Pixel normalization.** Raw cluster pixel values are keV, ranging up to ~1e6
for hot outlier pixels. `mlccd_models.GetPixelClusterData` (lab code, used
as-is) hardcodes `np.clip(intensity, 0, 2.0)` on whatever pixel values it's
given — with raw keV inputs, 99.9%+ of real in-cluster pixels blow past that
ceiling and collapse to the same clipped value, destroying the intensity
signal (measured directly: NRG stuck at ~51% test accuracy, chance level,
with raw keV inputs). Same root cause the CNN script already handles via
`CCDData.normalize()` — NRG just never had that step. `--normalize-percentile`
clips at that percentile of the training set's pixel distribution and
rescales to [0, 1] via `CCDData.normalize()` *before*
`prepare_energyflow_format()`, so real signal pixels land inside
`GetPixelClusterData`'s clip range instead of all collapsing to it.

**Energy threshold rescaling.** `--energy-threshold-kev` (still expressed in
raw keV on the CLI, for the same "4 sigma" Fermilab-noise-level convention
used elsewhere in this project) is rescaled by the same
`normalize_threshold_high` before being passed to `GetPixelClusterData` as
`threshold` — that function compares its `threshold` argument against
whatever pixel values it's actually given, which are the *normalized* ones
once `ccd_data.normalize()` has run.

## train_bdt.py

**Not a reproduction of a lab model.** `mlccd_models` ships no boosted-tree
model at all — only `CCDData.x_train_bdt`/`x_test_bdt`/`x_validation_bdt` as
feature-prep helpers for a BDT that would live outside the package. The
lab's actual BDT training code isn't in this dependency, and the package's
only other classical (non-neural) model, `ClassicalDiscriminator`, is a
2D-histogram discriminator — a different algorithm, not a BDT. This script
trains a plain `sklearn.ensemble.GradientBoostingClassifier` from scratch as
a stand-in,
using the same three features `CCDData.x_train_bdt` already selects
(`clusterEnergy`, `clusterSigmaX`, `clusterSigmaY`) — which are also exactly
the fields already present on `ClassificationRequestCluster`
(`total_energy`, `sigmaX`, `sigmaY`), so `classify_bdt()` needs no pixel math
at inference time, just those three numbers per cluster. Output is a single
`bdt.joblib` file.

```bash
uv run python tools/training/train_bdt.py \
    --dataset ~/Downloads/10x10_clusters_fermilab_bkg_and_tritium/\
fermilab_upnoised_quadrant_0_and_3_baseline_cut_unbalanced.pkl \
    --output-dir ~/lbnlvis-models/lbnl_tritium
```

`n_estimators`/`learning_rate`/`n_iter_no_change` match the lab's own
`boosted_decision_tree.ipynb` (500 / 0.05 / 20, cross-referenced from
`archive/MockPipelineReport.md`) rather than the ad-hoc smoke-test values
(200 / 0.1 / none) the first version of this script shipped with.
`random_state` stays tied to `--seed` (this project's own reproducibility
convention) rather than the lab's specific `random_state=100`.

## _ccd_dataset.py

Shared dataset-loading helper used by all three trainers above. Wraps two
real bugs found in the vendored `mlccd_models` package (0.5.0) while building
these scripts, so every trainer gets the workaround instead of
re-discovering it:

1. `CCDData.__init__(..., train_validation_test_fraction=(a, b, c))` forwards
   the whole 3-tuple as a single positional argument to
   `split_data(self, train_fraction, validation_fraction, test_fraction)`,
   which always raises `TypeError: missing 2 required positional arguments`.
   Constructing without that kwarg and calling `ccd_data.split_data(a, b, c)`
   afterward avoids the bug entirely.
2. `split_data()` assigns into `tracks_metadata.loc[train_indices, "split"]`,
   which raises `KeyError` unless `tracks_metadata` already has one row per
   image. A `.pkl`-loaded `CCDData` starts with an *empty* `tracks_metadata`
   (`read_pkl` sets it to `pd.DataFrame()`), so `add_cluster_metadata()`
   (which assigns columns of the right length, expanding the empty frame to
   match) must run before `split_data()`, not after.
