"""Shared dataset-loading helper for the tools/training/train_*.py scripts.

Wraps two real bugs found in the vendored ``mlccd_models`` package (0.5.0)
while building these scripts, so every trainer gets the workaround instead
of re-discovering it:

1. ``CCDData.__init__(..., train_validation_test_fraction=(a, b, c))``
   forwards the whole 3-tuple as a single positional argument to
   ``split_data(self, train_fraction, validation_fraction, test_fraction)``,
   which always raises ``TypeError: missing 2 required positional
   arguments``. Constructing without that kwarg and calling
   ``ccd_data.split_data(a, b, c)`` afterward avoids the bug entirely.
2. ``split_data()`` assigns into ``tracks_metadata.loc[train_indices, "split"]``,
   which raises ``KeyError`` unless ``tracks_metadata`` already has one row
   per image. A ``.pkl``-loaded ``CCDData`` starts with an *empty*
   ``tracks_metadata`` (``read_pkl`` sets it to ``pd.DataFrame()``), so
   ``add_cluster_metadata()`` (which assigns columns of the right length,
   expanding the empty frame to match) must run before ``split_data()``,
   not after.
"""

import mlccd_models


def load_dataset(
    dataset_path: str,
    train_fraction: float,
    validation_fraction: float,
    test_fraction: float,
    seed: int,
) -> "mlccd_models.CCDData":
    """Loads a ``.pkl``/``.pickle`` dataset and returns a split, metadata-populated CCDData.

    ``tracks_metadata`` (``clusterEnergy``/``clusterSigmaX``/``clusterSigmaY``/
    ``clusterMinSigma``/``clusterMaxSigma``) is populated from the raw keV pixel
    data before the train/validation/test split is assigned, in that order, to
    work around the two ``mlccd_models`` bugs documented above.
    """
    ccd_data = mlccd_models.CCDData(dataset_path, seed=seed)
    mlccd_models.add_cluster_metadata(ccd_data)
    ccd_data.split_data(train_fraction, validation_fraction, test_fraction)
    return ccd_data
