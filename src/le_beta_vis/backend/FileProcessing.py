import socket
import numpy as np
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.common.cluster_sigma import compute_cluster_sigmas
from le_beta_vis.common.EPSDataClasses import (
    FitsStoreRequest,
    ClusterStoreRequest,
)
from astropy.io import fits
from scipy.ndimage import label, maximum_position
import numpy as np
import os
from pathlib import Path
import zmq
import logging

logger = logging.getLogger(__name__)

def process_file(config_service: ConfigurationService, file: Path):
        config = config_service
        kev = config.get(key = "global:physics:kev_conversion") # Will be adjusted for real config service
        ped_width = config.get(key = "global:physics:ped_width")
        fits_name = file
        capture = CCDCaptureModel.load(file)
        fits_id = None
        process_context = zmq.Context()
        try:
            fits_id = store_fits(process_context, config, fits_name, capture, fits_id, kev, ped_width)
            cluster_fits(process_context, config, capture, fits_id, kev, ped_width)
        finally:
            process_context.term()

def store_fits(process_context: zmq.Context, config: ConfigurationService, fits_name: Path, capture: CCDCaptureModel,
               fits_id: int, kev: float, ped_width: float):
    """
    Stores ingested fits file into the fits_file table in the database.
    """
    socket = process_context.socket(zmq.REQ)
    try:
        socket.connect(config.get("eps:fits_ipc"))
        # Form JSON request with fits data, send to endpoint and grab response
        request = FitsStoreRequest(
                filename = fits_name,
                date= str(capture[0].info().captureDate()),
                min= float(min(capture[0].info().min, capture[1].info().min, capture[2].info().min, capture[3].info().min)),
                max= float(max(capture[0].info().max, capture[1].info().max, capture[2].info().max, capture[3].info().max)),
                exposure_time= str(capture[0].info().exposureDuration())
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
                 fits_id: int, kev: float, ped_width: float):
    """
    Iterates through HDUs, creating clusters from each
    """
    for hdu_index, hdu in enumerate(capture):
        data = hdu.rawData()
        # Label as a cluster if the data passes the four sigma threshold comparison to the background noise
        labeled_array, num_features = label(data > 4 * ped_width) # 4 sigma threshold
        for i in range(1, num_features + 1):
            # This will set each background value in the numpy array to zero and keep all features that pass the threshold
            # as their value
            cluster_image = np.where(labeled_array == i, data, 0)
            # Using 1 keV as a baseline to filter out smaller energy clusters, this is the threshold for tritium decay
            # This can be adjusted here to play with the total cluster results
            if (np.sum(cluster_image) * kev) < 1:
                continue
            # If the cluster passed the threshold and was stored as an image, calc max position
            try:
                max_pos = maximum_position(cluster_image, labels=labeled_array, index=i)
            except:
                continue
            # Extract region around the maximum to display
            y, x = max_pos
            # Check if the 10x10 region centered around max_pos would lie completely within the image
            # If the plot ends up smaller, the event is most likely not from tritium decay due to its size
            if y - 5 >= 0 and y + 5 <= data.shape[0] and x - 5 >= 0 and x + 5 <= data.shape[1]:
                y_start, y_end = y - 5, y + 5
                x_start, x_end = x - 5, x + 5
            # If cluster is bigger or smaller than a 10x10 image, such as with a muon, set start and ending coordinates
            # based on the indices of the array where there are min and max values
            else:
                indices = np.where(cluster_image > 0)
                y_start, y_end = np.min(indices[0]), np.max(indices[0]) + 1
                x_start, x_end = np.min(indices[1]), np.max(indices[1]) + 1

            #Ranges here can be adjusted based on the maximum size of the HDU display
            if x_end - x_start >= 3200 or y_end - y_start >= 550 or x_end - x_start <= 1 or y_end - y_start <= 1:
                continue

            # Extract a cluster centered at the maximum position, with and without background noise
            # pixels_around_cluster_with_noise = data[y_start:y_end, x_start:x_end]
            pixels_around_cluster_wo_noise = cluster_image[y_start:y_end, x_start:x_end]
            bounding_box = BoundingBox(y_end, x_start, y_start, x_end)

            # Calculate weighted mean sigma
            sigma_x, sigma_y = compute_cluster_sigmas(pixels_around_cluster_wo_noise)

            # Store the values, standard deviation in x and y, energy value, and other relevant info
            cluster_sigma_x = sigma_x
            cluster_sigma_y = sigma_y
            cluster_energy = np.sum(pixels_around_cluster_wo_noise)
            cluster_pixels = np.count_nonzero(pixels_around_cluster_wo_noise)
            cluster = Cluster(
                boundingBox=bounding_box,
                data=pixels_around_cluster_wo_noise,
                centerX=x,
                centerY=y,
                sigmaX=cluster_sigma_x,
                sigmaY=cluster_sigma_y,
                energy=cluster_energy,
                pixelCount=cluster_pixels,
                fitsId=fits_id,
                hdu_id=hdu_index,
            )
            store_cluster(config, process_context, cluster)

def store_cluster(config: ConfigurationService, process_context: zmq.Context, cluster: "Cluster"):
    """
    Stores ingested clusters into the clusters table in the database.
    """
    socket = process_context.socket(zmq.REQ)
    try:
        socket.connect(config.get("eps:cluster_ipc"))
        # Form JSON request with cluster data, send to endpoint and grab response
        request = ClusterStoreRequest(
                data = None,
                hdu_id= cluster.hdu_id,
                bounding_box= {
                    "top": int(cluster.boundingBox.top),
                    "left":int(cluster.boundingBox.left),
                    "bottom": int(cluster.boundingBox.bottom),
                    "right": int(cluster.boundingBox.right)
                },
                sigma_x= float(cluster.sigmaX),
                sigma_y= float(cluster.sigmaY),
                total_energy= float(cluster.energy),
                total_pixels= int(cluster.pixelCount),
                fits_id= cluster.fitsId,
                classification= cluster.classification
        )
        request_dict = request.to_eps_dict()
        socket.send_json(request_dict)
        response = socket.recv_json()
        if response["result"] == "success":
            cluster.clusterId = response["cluster_id"]
            logger.info(f"Cluster ID {cluster.clusterId} stored in database.")
        else:
            logger.warning(f"There was an issue communicating with the EPS. Due to {response['error']}")
    finally:
        socket.close()
