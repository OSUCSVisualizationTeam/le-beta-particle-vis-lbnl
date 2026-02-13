import numpy as np
from le_beta_vis.common.CCDCaptureModel import CCDCaptureModel
from le_beta_vis.common.ConfigurationService import ConfigurationService
import mysql.connector
from astropy.io import fits
from scipy.ndimage import label, maximum_position
import numpy as np
import os
from pathlib import Path

class ProcessFile():
    """
    FITS ingress processing operation class, saves data from file path and clusters
    """
    def __init__(self, config_service: ConfigurationService, file: Path):
        self.kev = config_service.get(key = "global:physics:kev_conversion") # Will be adjusted for real config service
        self.ped_width = config_service.get(key = "global:physics:ped_width")
        self.db = config_service.get(key = "global:db:connection_string")
        self.capture = CCDCaptureModel.load(file)
        self.clusters = []
        self.cluster_fits()
        self.fits_id = None

    def store_fits(self):
        """
        Stores ingested fits file into the fits_file table in the database.
        """
        # This will most likely need to be reworked with the configuration service to pull accurate values
        # Pending decision on storing db logins
        try:
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="root",
                database="lbnlfits"
            )
            cursor = conn.cursor()
            date = self.capture[0].captureDate()
            minimum = min(self.capture[0].info.min, self.capture[1].info.min, self.capture[2].info.min, self.capture[3].info.min)
            maximum = max(self.capture[0].info.max, self.capture[1].info.max, self.capture[2].info.max, self.capture[3].info.max) 
            exposure_time = self.capture[0].exposureDuration()
            proc_args = (date, minimum, maximum, exposure_time, (0, 'INT'))
            cursor.callproc("insert_fits", proc_args)

            for result in cursor.stored_results():
                id = result.fetchone()
                if id > 0:
                    self.fits_id = id
                else:
                    raise FailedProcException
            
            # Commit results and close connection
            conn.commit()
            cursor.close()
            conn.close()

        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")

    def cluster_fits(self):
        """
        Iterates through HDUs, creating clusters from each
        """
        for hdu in self.capture:
            data = hdu.rawData()
            # Label as a cluster if the data passes the four sigma threshold comparison to the background noise
            labeled_array, num_features = label(data > 4 * self.ped_width) # 4 sigma threshold
            for i in range(num_features):
                # This will set each background value in the numpy array to zero and keep all features that pass the threshold
                # as their value
                cluster_image = np.where(labeled_array == i, data, 0)
                # Using 1 keV as a baseline to filter out smaller energy clusters, this is the threshold for tritium decay
                # This can be adjusted here to play with the total cluster results
                if (np.sum(cluster_image) * self.kev) < 1:
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

                # Calculate weighted mean sigma
                sigma_x, sigma_y = self.calc_sigmas(pixels_around_cluster_wo_noise)

                # Store the values, standard deviation in x and y, energy value, and other relevant info
                cluster_sigma_x = sigma_x
                cluster_sigma_y = sigma_y
                cluster_energy = np.sum(pixels_around_cluster_wo_noise)
                cluster_pixels = np.count_nonzero(pixels_around_cluster_wo_noise)
                self.clusters.append(Cluster(cluster_sigma_x, cluster_sigma_y, cluster_energy, cluster_pixels))

    def calc_sigmas(self, dtrack):
        """
        Calculates standard deviation from tracks around cluster
        """
        x, y = np.meshgrid(np.arange(dtrack.shape[1]), np.arange(dtrack.shape[0]))
        sum_weights = np.sum(dtrack)
        mean_x = np.sum(x * dtrack) / sum_weights
        mean_y = np.sum(y * dtrack) / sum_weights
        sigma_x = np.sqrt(np.sum(dtrack * (x - mean_x)**2) / sum_weights)
        sigma_y = np.sqrt(np.sum(dtrack * (y - mean_y)**2) / sum_weights)
        return sigma_x, sigma_y

class Cluster():
    """
    Cluster class with methods for classification and storage
    """
    def __init__(self,
                 sigmaX: float,
                 sigmaY: float,
                 energy: float,
                 pixels: int
                 ):
        self.sigmaX = sigmaX
        self.sigmaY = sigmaY
        self.total_energy = energy
        self.total_pixels = pixels
        # debug
        print(f"Sigma x: {self.sigmaX}\nSigma Y: {self.sigmaY}\nEnergy: {self.total_energy}\n Pixels: {self.total_pixels}")

    def classify_clusters(self):
        """
        Run clusters through classification models to save in database.
        """
        raise NotImplementedError

    def store_clusters(self, fitsID: int):
        """
        Stores ingested clusters into the clusters table in the database.
        """
        raise NotImplementedError

class FailedProcException(Exception):
    """
    Subclassed exception to handle failed procedure calls in the database
    """
    def __init__(self, message="There was an issue running the stored procedure."):
        super().__init__(message)
        self.message = message
