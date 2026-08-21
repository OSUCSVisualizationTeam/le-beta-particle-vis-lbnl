"""Shared dataset-loading helper for the tools/training/train_*.py scripts.

Works around two real bugs found in the vendored ``mlccd_models`` package
(0.5.0). See ``tools/training/README.md`` for the details.
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
