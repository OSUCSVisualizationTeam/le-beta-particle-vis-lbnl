import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Tuple

import numpy as np

from le_beta_vis.common.ClassifierDataClasses import ClassificationRequestCluster
from le_beta_vis.common.ClassifierService import (
    ClassificationBatchResult,
    ClassificationResult,
    ClassificationScore,
    ClassifierService,
    CompletionCallback,
    ErrorCallback,
)
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.ParticleType import ParticleType

logger = logging.getLogger(__name__)

_DEFAULT_LBNL_MODEL_WEIGHTS_DIR = "~/lbnlvis-models/lbnl_tritium"
"""Fallback for `classifier:lbnl_model_weights_dir` if unset in config.
Mirrors the default in `config/defaults.yaml`. Deliberately not a guessed
real path (the trained artifacts are external, produced by
tools/training/train_*.py and never shipped in this repo) — a plain
home-relative placeholder that `os.path.expanduser()` resolves correctly on
every platform, same rationale as `InitializePolling._DEFAULT_POLLING_LOCATION`."""

_CNN_MODEL_FILENAME = "cnn.keras"
_CNN_META_FILENAME = "cnn.meta.json"
_NRG_WEIGHTS_FILENAME = "nrg.weights.h5"
_NRG_META_FILENAME = "nrg.meta.json"
_BDT_MODEL_FILENAME = "bdt.joblib"

_CNN_MODEL_NAME = "CNN"
_NRG_MODEL_NAME = "NRG"
_BDT_MODEL_NAME = "BDT"

_BDT_FEATURE_COLUMNS = ["clusterEnergy", "clusterSigmaX", "clusterSigmaY"]
"""Column order the BDT was trained on (CCDData.x_train_bdt's own default columns) —
named to match, or sklearn warns that predict_proba() got an unnamed array."""

_EXPECTED_CLUSTER_SHAPE = (10, 10)
"""Both the CNN and NRG models were trained on exactly 10x10 cluster crops (issue #54's own
acceptance criteria). FileProcessing's cluster extractor also emits larger, variably-shaped
crops for oversized events that don't fit a 10x10 window (e.g. muon tracks) — those can't be
stacked into one batch array and can't be meaningfully scored by either model, so they're
filtered out per-cluster rather than failing classification for the whole batch."""


def _conforming_pixel_batch(
    clusters: List[ClassificationRequestCluster],
) -> Tuple[List[int], np.ndarray]:
    """Splits clusters by whether their data matches _EXPECTED_CLUSTER_SHAPE and stacks just the
    conforming ones into one array. Returns (original indices of conforming clusters, stacked
    float32 array) — both empty if none conform."""
    conforming_indices = [
        i
        for i, c in enumerate(clusters)
        if len(c.data) == _EXPECTED_CLUSTER_SHAPE[0]
        and all(len(row) == _EXPECTED_CLUSTER_SHAPE[1] for row in c.data)
    ]
    if not conforming_indices:
        return [], np.empty((0,) + _EXPECTED_CLUSTER_SHAPE, dtype=np.float32)
    if len(conforming_indices) < len(clusters):
        logger.debug(
            "Skipping %d of %d clusters for pixel-based classification: shape != %s "
            "(likely an oversized event crop, e.g. a muon track).",
            len(clusters) - len(conforming_indices),
            len(clusters),
            _EXPECTED_CLUSTER_SHAPE,
        )
    images = np.array([clusters[i].data for i in conforming_indices], dtype=np.float32)
    return conforming_indices, images


class LBNLTritiumClassifierService(ClassifierService):
    """Runs the lab's tritium classifiers against artifacts trained by tools/training/.

    Weights are never shipped in this repo (external, lab-scale training
    data) — they're read from ``classifier:lbnl_model_weights_dir`` at
    construction. All three models are loaded eagerly here rather than
    lazily on first use, so a broken weights directory is caught and logged
    once at startup instead of silently on the first classify_* call (see
    wiki/Front-Design-Startup-Readiness.md's pre-warm discussion). A missing
    or unloadable model is not a constructor error — that model is simply
    unavailable for the life of this instance, and every cluster scored
    against it comes back with ``score=None`` (counted in
    ``ClassificationBatchResult.failed``), matching the ABC's per-cluster
    failure isolation contract.

    Model objects are injectable so unit tests can substitute fake
    ``.predict()``/``.predict_proba()`` stubs without needing real weight
    files or a TensorFlow-heavy CI run.
    """

    def __init__(
        self,
        config: ConfigurationService,
        cnn_model: Any = None,
        cnn_meta: Optional[dict] = None,
        nrg_model: Any = None,
        nrg_meta: Optional[dict] = None,
        bdt_model: Any = None,
    ) -> None:
        weights_dir = os.path.expanduser(
            config.get("classifier:lbnl_model_weights_dir", _DEFAULT_LBNL_MODEL_WEIGHTS_DIR)
        )
        inference_workers = config.get_int(
            "classifier:inference_workers", 1, minimum=1, maximum=4
        )
        self._executor = ThreadPoolExecutor(
            max_workers=inference_workers, thread_name_prefix="LBNLTritiumClassifier"
        )

        if cnn_model is not None:
            self._cnn_model, self._cnn_meta = cnn_model, cnn_meta or {}
        else:
            self._cnn_model, self._cnn_meta = self._load_cnn(weights_dir)

        if nrg_model is not None:
            self._nrg_model, self._nrg_meta = nrg_model, nrg_meta or {}
        else:
            self._nrg_model, self._nrg_meta = self._load_nrg(weights_dir)

        self._bdt_model = bdt_model if bdt_model is not None else self._load_bdt(weights_dir)

    def unavailable_models(self) -> List[str]:
        """Names of the CNN/NRG/BDT models that failed to load, if any."""
        missing = []
        if self._cnn_model is None:
            missing.append(_CNN_MODEL_NAME)
        if self._nrg_model is None:
            missing.append(_NRG_MODEL_NAME)
        if self._bdt_model is None:
            missing.append(_BDT_MODEL_NAME)
        return missing

    @staticmethod
    def _load_cnn(weights_dir: str) -> Tuple[Any, dict]:
        """Loads cnn.keras + its cnn.meta.json normalization sidecar, or (None, {}) on failure."""
        model_path = os.path.join(weights_dir, _CNN_MODEL_FILENAME)
        meta_path = os.path.join(weights_dir, _CNN_META_FILENAME)
        try:
            import tensorflow as tf

            model = tf.keras.models.load_model(model_path)
            with open(meta_path) as f:
                meta = json.load(f)
            return model, meta
        except Exception:
            logger.exception("Could not load CNN model from %s; classify_cnn will report failures.", model_path)
            return None, {}

    @staticmethod
    def _load_nrg(weights_dir: str) -> Tuple[Any, dict]:
        """Loads nrg.meta.json + reconstructs the PFN architecture + nrg.weights.h5, or (None, {})."""
        weights_path = os.path.join(weights_dir, _NRG_WEIGHTS_FILENAME)
        meta_path = os.path.join(weights_dir, _NRG_META_FILENAME)
        try:
            with open(meta_path) as f:
                meta = json.load(f)
            import mlccd_models

            pfn = mlccd_models.PFNModel(
                input_dim=meta["input_dim"],
                Phi_sizes=tuple(meta["phi_sizes"]),
                F_sizes=tuple(meta["f_sizes"]),
                output_dim=1,
            )
            pfn.model.load_weights(weights_path)
            return pfn, meta
        except Exception:
            logger.exception("Could not load NRG model from %s; classify_nrg will report failures.", weights_path)
            return None, {}

    @staticmethod
    def _load_bdt(weights_dir: str) -> Any:
        """Loads bdt.joblib, or None on failure."""
        model_path = os.path.join(weights_dir, _BDT_MODEL_FILENAME)
        try:
            import joblib

            return joblib.load(model_path)
        except Exception:
            logger.exception("Could not load BDT model from %s; classify_bdt will report failures.", model_path)
            return None

    def classify_cnn(
        self,
        clusters: List[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Classifies clusters with the raw-pixel CNN model."""
        self._classify(clusters, _CNN_MODEL_NAME, self._predict_cnn, on_complete, on_error)

    def classify_nrg(
        self,
        clusters: List[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Classifies clusters with the energy-flow (PFN) model."""
        self._classify(clusters, _NRG_MODEL_NAME, self._predict_nrg, on_complete, on_error)

    def classify_bdt(
        self,
        clusters: List[ClassificationRequestCluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Classifies clusters with the gradient-boosted-tree model."""
        self._classify(clusters, _BDT_MODEL_NAME, self._predict_bdt, on_complete, on_error)

    def _classify(
        self,
        clusters: List[ClassificationRequestCluster],
        model_name: str,
        predict_fn,
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback],
    ) -> None:
        """Runs predict_fn on a background thread, routed through the shared bounded
        inference pool, and reports per-cluster results via on_complete.

        The outer daemon thread satisfies the ABC's "callbacks fire from a background
        thread" contract for every call; the inner executor.submit(...) is what actually
        bounds concurrent model inference (classifier:inference_workers) across every
        FileProcessing thread and dialog invocation sharing this service instance —
        the burst-throttling mechanism.
        """

        def _run() -> None:
            try:
                scores = self._executor.submit(predict_fn, clusters).result()
            except Exception as exc:
                if on_error:
                    on_error(exc)
                return

            results = []
            failed = 0
            for cluster, score in zip(clusters, scores):
                if score is None:
                    results.append(ClassificationResult(cluster.cluster_id, model_name, None))
                    failed += 1
                else:
                    results.append(
                        ClassificationResult(
                            cluster.cluster_id,
                            model_name,
                            ClassificationScore(ParticleType.TRITIUM, score),
                        )
                    )
            on_complete(ClassificationBatchResult(results, len(clusters), failed))

        threading.Thread(target=_run, daemon=True).start()

    def _predict_cnn(self, clusters: List[ClassificationRequestCluster]) -> List[Optional[float]]:
        """Batched CNN inference. Replays the exact normalization used at training time.
        Clusters that aren't a 10x10 crop (see _conforming_pixel_batch) score None rather than
        failing the whole batch."""
        scores: List[Optional[float]] = [None] * len(clusters)
        if self._cnn_model is None:
            return scores
        conforming_indices, images = _conforming_pixel_batch(clusters)
        if not conforming_indices:
            return scores
        images = images.reshape(images.shape[0], images.shape[1], images.shape[2], 1)
        low = self._cnn_meta.get("normalize_threshold_low", 0.0)
        high = self._cnn_meta.get("normalize_threshold_high", 1.0)
        images = np.clip(images, low, high)
        images = (images - low) / (high - low)
        predictions = self._cnn_model.predict(images, verbose=0).ravel()
        for idx, prediction in zip(conforming_indices, predictions):
            scores[idx] = float(prediction)
        return scores

    def _predict_nrg(self, clusters: List[ClassificationRequestCluster]) -> List[Optional[float]]:
        """Batched NRG (energy-flow) inference. Replays the exact preprocessing used at training
        time (normalize_threshold_low/high, threshold, pixels_around_brightest_pixel — all from
        nrg.meta.json). Normalization matters here: GetPixelClusterData hardcodes
        np.clip(intensity, 0, 2.0), and raw keV pixel values blow past that ceiling for ~all
        real signal pixels, collapsing the intensity channel to a constant — training measured
        this directly (~51% accuracy, chance level, without normalization first). Clusters that
        aren't a 10x10 crop (see _conforming_pixel_batch) score None rather than failing the
        whole batch."""
        scores: List[Optional[float]] = [None] * len(clusters)
        if self._nrg_model is None:
            return scores
        import mlccd_models

        conforming_indices, images = _conforming_pixel_batch(clusters)
        if not conforming_indices:
            return scores
        low = self._nrg_meta.get("normalize_threshold_low", 0.0)
        high = self._nrg_meta.get("normalize_threshold_high", 1.0)
        images = np.clip(images, low, high)
        images = (images - low) / (high - low)
        point_clouds = mlccd_models.GetPixelClusterData(
            images,
            threshold=self._nrg_meta["threshold"],
            pixels_around_brightest_pixel=self._nrg_meta["pixels_around_brightest_pixel"],
        )
        predictions = self._nrg_model.predict(point_clouds).ravel()
        for idx, prediction in zip(conforming_indices, predictions):
            scores[idx] = float(prediction)
        return scores

    def _predict_bdt(self, clusters: List[ClassificationRequestCluster]) -> List[Optional[float]]:
        """Batched BDT inference over [total_energy, sigmaX, sigmaY] — already present on
        every ClassificationRequestCluster, no pixel math needed."""
        if self._bdt_model is None:
            return [None] * len(clusters)
        import pandas as pd

        features = pd.DataFrame(
            [[c.total_energy, c.sigmaX, c.sigmaY] for c in clusters],
            columns=_BDT_FEATURE_COLUMNS,
        )
        predictions = self._bdt_model.predict_proba(features)[:, 1]
        return [float(p) for p in predictions]
