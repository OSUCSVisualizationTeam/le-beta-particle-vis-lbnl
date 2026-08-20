import logging
import threading
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
import zmq
from scipy.ndimage import label, maximum_position

from le_beta_vis.backend.ClusterStorageBuffer import ClusterStorageBuffer, FlushCallback
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ClassifierDataClasses import ClassificationRequestCluster
from le_beta_vis.common.ClassifierService import ClassificationBatchResult, ClassifierService
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.cluster_sigma import compute_cluster_sigmas
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.EPSDataClasses import (
    FitsStoreRequest,
    ClusterStoreRequest,
    BulkClusterStoreRequest,
)
from le_beta_vis.common.ParticleType import classify_particle

logger = logging.getLogger(__name__)

ClusterStorageBufferFactory = Callable[[int, FlushCallback], ClusterStorageBuffer]
"""Builds a ClusterStorageBuffer given a capacity and flush callback.

FileProcessing never constructs a concrete ClusterStorageBuffer itself — the caller (ultimately
InitializePolling.py) injects which implementation to use, so it can be swapped without touching
this file.
"""


def process_file(
    config_service: ConfigurationService,
    file: Path,
    cluster_storage_buffer_factory: ClusterStorageBufferFactory,
    classifier_service: ClassifierService,
):
    config = config_service
    kev = config.get(key="global:physics:kev_conversion")  # Will be adjusted for real config service
    ped_width = config.get(key="global:physics:ped_width")
    fits_name = file
    process_context = zmq.Context()
    try:
        capture = CCDCaptureModel.load(file)
        fits_id = None
        fits_id = store_fits(process_context, config, fits_name, capture, fits_id, kev, ped_width)
        cluster_fits(
            process_context, config, capture, fits_id, kev, ped_width,
            cluster_storage_buffer_factory, classifier_service,
        )
    finally:
        process_context.term()


def store_fits(process_context: zmq.Context, config: ConfigurationService, fits_name: Path, capture: CCDCaptureModel,
               fits_id: int, kev: float, ped_width: float):
    """Stores ingested fits file into the fits_file table in the database."""
    socket = process_context.socket(zmq.REQ)
    timeout_ms = config.get_int("eps:timeout_ms", 5000)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
    socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
    try:
        socket.connect(config.get("eps:fits_ipc"))
        # Form JSON request with fits data, send to endpoint and grab response
        request = FitsStoreRequest(
            filename=fits_name,
            date=str(capture[0].info().captureDate()),
            min=float(min(capture[0].info().min, capture[1].info().min, capture[2].info().min, capture[3].info().min)),
            max=float(max(capture[0].info().max, capture[1].info().max, capture[2].info().max, capture[3].info().max)),
            exposure_time=str(capture[0].info().exposureDuration())
        )
        request_dict = request.to_eps_dict()
        socket.send_json(request_dict)
        logger.info("New store FITS request sent to EPS.")
        response = socket.recv_json()
        if response["result"] == "success":
            fits_id = response["fits_id"]
            logger.info(f"Fits ID {fits_id} stored in database.")
            return fits_id
        else:
            logger.warning(f"There was an issue communicating with the EPS. Due to {response['error']}")
    except Exception as e:
        logger.warning(f"There was an issue communicating with the EPS. Due to {e}")
    finally:
        socket.close()


def cluster_fits(process_context: zmq.Context, config: ConfigurationService, capture: CCDCaptureModel,
                 fits_id: int, kev: float, ped_width: float,
                 cluster_storage_buffer_factory: ClusterStorageBufferFactory,
                 classifier_service: ClassifierService):
    """Iterates through HDUs, creating clusters from each, classifying them, and buffering them for
    batched storage in the EPS.

    Clusters are classified per-HDU, in one batch per model, before being handed to the
    ClusterStorageBuffer — classification travels in the same Storage/BulkStorage EPS round-trip
    that creates the row, matching this project's store_cluster (not update_classification)
    convention for freshly-extracted clusters that have never been persisted.
    """
    buffer_size = config.get_int("eps:cluster_storage_buffer_size", 32, minimum=16, maximum=2000)
    socket = process_context.socket(zmq.REQ)
    timeout_ms = config.get_int("eps:timeout_ms", 5000)
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
    socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
    socket.connect(config.get("eps:cluster_ipc"))
    try:
        with cluster_storage_buffer_factory(
            buffer_size, lambda batch: _flush_cluster_batch(socket, batch)
        ) as buffer:
            for hdu_index, hdu in enumerate(capture):
                hdu_clusters = _extract_hdu_clusters(hdu, hdu_index, fits_id, kev, ped_width)
                _classify_clusters(classifier_service, hdu_clusters)
                for cluster in hdu_clusters:
                    buffer.add(cluster)
    finally:
        socket.close()


def _extract_hdu_clusters(
    hdu, hdu_index: int, fits_id: int, kev: float, ped_width: float,
) -> List[Cluster]:
    """Labels connected-component clusters in one HDU and builds a Cluster per surviving feature."""
    data = hdu.rawData()
    # Label as a cluster if the data passes the four sigma threshold comparison to the background noise
    labeled_array, num_features = label(data > 4 * ped_width)  # 4 sigma threshold
    clusters = []
    for i in range(1, num_features + 1):
        # This will set each background value in the numpy array to zero and keep all features that pass
        # the threshold as their value
        cluster_image = np.where(labeled_array == i, data, 0)
        # Using 1 keV as a baseline to filter out smaller energy clusters, this is the threshold for
        # tritium decay. This can be adjusted here to play with the total cluster results
        if (np.sum(cluster_image) * kev) < 1:
            continue
        # If the cluster passed the threshold and was stored as an image, calc max position
        try:
            max_pos = maximum_position(cluster_image, labels=labeled_array, index=i)
        except BaseException:
            continue
        # Extract region around the maximum to display
        y, x = max_pos
        # Check if the 10x10 region centered around max_pos would lie completely within the image
        # If the plot ends up smaller, the event is most likely not from tritium decay due to its size
        if y - 5 >= 0 and y + 5 <= data.shape[0] and x - 5 >= 0 and x + 5 <= data.shape[1]:
            y_start, y_end = y - 5, y + 5
            x_start, x_end = x - 5, x + 5
        # If cluster is bigger or smaller than a 10x10 image, such as with a muon, set start and ending
        # coordinates based on the indices of the array where there are min and max values
        else:
            indices = np.where(cluster_image > 0)
            y_start, y_end = np.min(indices[0]), np.max(indices[0]) + 1
            x_start, x_end = np.min(indices[1]), np.max(indices[1]) + 1

        # Ranges here can be adjusted based on the maximum size of the HDU display
        if x_end - x_start >= 3200 or y_end - y_start >= 550 or x_end - x_start <= 1 or y_end - y_start <= 1:
            continue

        # Extract a cluster centered at the maximum position, with and without background noise
        # pixels_around_cluster_with_noise = data[y_start:y_end, x_start:x_end]
        # .copy() is required: a bare slice is a *view* into cluster_image, which is the same
        # size as the full HDU frame (freshly allocated on every loop iteration via np.where
        # above). Without copying, every stored Cluster.data keeps its entire multi-MB parent
        # frame alive via numpy's view-base reference — with ~1000+ clusters per dense HDU this
        # explodes to tens of GB and OOM-kills the process. Confirmed by direct reproduction.
        pixels_around_cluster_wo_noise = cluster_image[y_start:y_end, x_start:x_end].copy()
        bounding_box = BoundingBox(y_end, x_start, y_start, x_end)

        # Calculate weighted mean sigma
        sigma_x, sigma_y = compute_cluster_sigmas(pixels_around_cluster_wo_noise)

        # Store the values, standard deviation in x and y, energy value, and other relevant info
        cluster_energy = np.sum(pixels_around_cluster_wo_noise)
        cluster_pixels = np.count_nonzero(pixels_around_cluster_wo_noise)
        clusters.append(
            Cluster(
                boundingBox=bounding_box,
                data=pixels_around_cluster_wo_noise,
                centerX=x,
                centerY=y,
                sigmaX=sigma_x,
                sigmaY=sigma_y,
                energy=cluster_energy,
                pixelCount=cluster_pixels,
                fitsId=fits_id,
                hdu_id=hdu_index,
            )
        )
    return clusters


def _classify_clusters(classifier_service: ClassifierService, clusters: List[Cluster]) -> None:
    """Classifies a batch of freshly-extracted clusters and writes per-model scores (and the
    derived aggregate label) back onto each Cluster in place."""
    if not clusters:
        return

    request_clusters = [
        ClassificationRequestCluster(
            data=cluster.data.tolist(),
            cluster_id=i,
            sigmaX=float(cluster.sigmaX),
            sigmaY=float(cluster.sigmaY),
            total_energy=float(cluster.energy),
            total_pixels=int(cluster.pixelCount),
        )
        for i, cluster in enumerate(clusters)
    ]

    cnn_batch = _call_classifier(classifier_service.classify_cnn, request_clusters)
    nrg_batch = _call_classifier(classifier_service.classify_nrg, request_clusters)
    bdt_batch = _call_classifier(classifier_service.classify_bdt, request_clusters)

    for i, cluster in enumerate(clusters):
        cluster.cnnClassification = _confidence_at(cnn_batch, i)
        cluster.nrgClassification = _confidence_at(nrg_batch, i)
        cluster.bdtClassification = _confidence_at(bdt_batch, i)
        particle_type, _ = classify_particle(cluster)
        cluster.classification = particle_type.name


def _call_classifier(classify_fn, request_clusters: List[ClassificationRequestCluster]) -> Optional[ClassificationBatchResult]:
    """Blocks the calling thread until classify_fn's async callback fires.

    Mirrors RawClusterClassificationViewModel._call_model's threading.Event latch — the
    ClassifierService contract fires on_complete/on_error from a background thread regardless of
    implementation, so this works whether that thread is the classifier's own or the calling thread
    itself (as MockClassifierService currently does).
    """
    result: Optional[ClassificationBatchResult] = None
    latch = threading.Event()

    def on_complete(batch: ClassificationBatchResult) -> None:
        nonlocal result
        result = batch
        latch.set()

    def on_error(exc: Exception) -> None:
        logger.warning(f"Classifier model error during file processing: {exc}")
        latch.set()

    classify_fn(request_clusters, on_complete, on_error)
    latch.wait()
    return result


def _confidence_at(batch: Optional[ClassificationBatchResult], index: int) -> float:
    """Extracts one cluster's confidence score from a batch result, defaulting to 0.0 (Cluster's
    cnn/nrg/bdtClassification fields are plain floats, not Optional)."""
    if batch is None:
        return 0.0
    score = batch.results[index].score
    return score.confidence if score is not None else 0.0


def _flush_cluster_batch(socket: zmq.Socket, clusters: List["Cluster"]) -> List[Optional[int]]:
    """Sends a batch of buffered clusters to the EPS in one BulkStorage round-trip and assigns the
    returned cluster_ids back onto each Cluster in order."""
    requests = [
        ClusterStoreRequest(
            data=None,
            hdu_id=cluster.hdu_id,
            bounding_box={
                "top": int(cluster.boundingBox.top),
                "left": int(cluster.boundingBox.left),
                "bottom": int(cluster.boundingBox.bottom),
                "right": int(cluster.boundingBox.right)
            },
            sigma_x=float(cluster.sigmaX),
            sigma_y=float(cluster.sigmaY),
            total_energy=float(cluster.energy),
            total_pixels=int(cluster.pixelCount),
            fits_id=cluster.fitsId,
            classification=cluster.classification,
            cnn_classification=cluster.cnnClassification,
            nrg_classification=cluster.nrgClassification,
            bdt_classification=cluster.bdtClassification,
        )
        for cluster in clusters
    ]
    try:
        socket.send_json(BulkClusterStoreRequest(clusters=requests).to_eps_dict())
        response = socket.recv_json()
    except zmq.ZMQError as err:
        logger.warning(f"There was an issue communicating with the EPS during bulk cluster storage. Due to {err}")
        return [None] * len(clusters)

    cluster_ids = response.get("cluster_ids") or [None] * len(clusters)
    for cluster, cluster_id in zip(clusters, cluster_ids):
        cluster.clusterId = cluster_id
    if response.get("result") != "success":
        logger.warning(f"Cluster batch storage returned '{response.get('result')}'. Due to {response.get('error')}")
    return cluster_ids
