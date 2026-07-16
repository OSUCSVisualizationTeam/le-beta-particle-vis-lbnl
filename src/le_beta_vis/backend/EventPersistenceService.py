from le_beta_vis.common.ZMQEventHandlerClient import DEFAULT_EVENT_PUB_ENDPOINT
import dataclasses
import mysql.connector
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.common.StartupIPCBindRegistry import bind_tracked_ipc_socket
from le_beta_vis.common.EPSDataClasses import (
    ClusterPagedQueryFilter,
    ClusterQueryFilter,
    ClusterRecentQueryFilter,
    FitsQueryFilter,
    FitsClusterQueryFilter,
    FitsStoreRequest,
    ClusterStoreRequest,
    ClassificationUpdateRequest,
    EPSClusterRecord,
    EPSFitsRecord,
    PagedRetrieveClustersResponse,
)
from le_beta_vis.backend.PagedClusterRetrieval import (
    paged_retrieve_clusters as _paged_retrieve_clusters,
)
import os
import zmq
import numpy as np
import logging
from datetime import datetime
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


_DATE_FILTER_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_date_filter(
    date: Optional[dict],
) -> Optional[Tuple[datetime, datetime]]:
    """Validates and parses a date-range filter from an EPS request.

    Returns ``(start, end)`` as ``datetime`` objects when both keys are
    present and well-formed, or ``None`` when no date filter was supplied
    (``None``, empty dict, or both keys ``None``). Raises ``ValueError``
    or ``TypeError`` on malformed input so the calling retrieve_* method
    can surface a clean failure response to the client instead of a
    confusing MySQL error.
    """
    if not date:
        return None
    start = date.get("start")
    end = date.get("end")
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise ValueError("date filter requires both 'start' and 'end'")
    if not isinstance(start, str) or not isinstance(end, str):
        raise TypeError(
            "date filter 'start' and 'end' must be strings"
        )
    try:
        start_dt = datetime.strptime(start, _DATE_FILTER_FORMAT)
        end_dt = datetime.strptime(end, _DATE_FILTER_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"date filter must use format '{_DATE_FILTER_FORMAT}': {exc}"
        )
    if start_dt > end_dt:
        raise ValueError("date filter 'start' must be <= 'end'")
    return start_dt, end_dt


class FailedProcException(Exception):
    """Subclassed exception to handle failed procedure calls in the database."""

    def __init__(self, message="There was an issue running the stored procedure."):
        super().__init__(message)
        self.message = message


class EventPersistence:
    """This class defines the EventPersistenceService that interfaces with the database.

    It is responsible for the storage and retrieval of FITS and cluster information
    """

    def __init__(self):
        self.config = YAMLBackedConfigurationService()
        self.db_host = self.config.get("global:db:hostname")
        self.db_user = self.config.get("global:db:username")
        self.db_password = self.config.get("global:db:password")
        self.database = self.config.get("global:db:database")
        self.conn = None

        self.conn = self.db_connect()  # connect to DB before listening loop
        self.initialize_server()

    def initialize_server(self):
        """Initialize the zmq server endpoint socket to listen for requests."""
        context_manager = zmq.Context()
        fits_socket = None
        cluster_socket = None
        command_socket = None

        try:
            fits_socket = context_manager.socket(zmq.REP)
            bind_tracked_ipc_socket(fits_socket, self.config, "eps:fits_ipc")
            cluster_socket = context_manager.socket(zmq.REP)
            bind_tracked_ipc_socket(cluster_socket, self.config, "eps:cluster_ipc")
            command_socket = context_manager.socket(zmq.REP)
            bind_tracked_ipc_socket(command_socket, self.config, "eps:command_ipc")

            socket_poller = zmq.Poller()
            socket_poller.register(fits_socket, zmq.POLLIN)
            socket_poller.register(cluster_socket, zmq.POLLIN)
            socket_poller.register(command_socket, zmq.POLLIN)

            EPS_is_active = True

            while True:
                try:
                    # timeout can be adjusted for performance
                    sockets = dict(socket_poller.poll(timeout=100))

                    if cluster_socket in sockets:
                        request = cluster_socket.recv_json()
                        if not EPS_is_active:
                            cluster_socket.send_json({"Error": "Server is stopped."})
                        else:
                            self.cluster_event(request, cluster_socket)

                    if fits_socket in sockets:
                        request = fits_socket.recv_json()
                        if not EPS_is_active:
                            fits_socket.send_json({"Error": "Server is stopped."})
                        else:
                            self.fits_event(request, fits_socket)

                    if command_socket in sockets:
                        request = command_socket.recv_json()
                        if request.get("Command") == "Kill":
                            command_socket.send_json({"Action": "Killed"})
                            break
                        elif request.get("Command") == "Stop":
                            EPS_is_active = False
                            command_socket.send_json({"Action": "Server stopped"})
                        elif request.get("Command") == "Start" and not EPS_is_active:
                            EPS_is_active = True
                            command_socket.send_json({"Action": "Server started"})
                        else:
                            command_socket.send_json({"Error": "Invalid request"})
                except zmq.ZMQError as err:
                    print(f"ERROR: {str(err)}")
        finally:
            if cluster_socket:
                cluster_socket.close()
            if fits_socket:
                fits_socket.close()
            if command_socket:
                command_socket.close()
            context_manager.term()

    def db_connect(self):
        """Opens a connection to the database with the values from the configuration."""
        try:
            conn = mysql.connector.connect(
                host=self.db_host,
                user=self.db_user,
                password=self.db_password,
                database=self.database,
            )
            return conn
        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")

    def cluster_event(self, request: dict, socket: zmq.Socket):
        """Processes a requested cluster event and calls storage or retrieval of cluster."""
        logger.info("Cluster request received by EPS.")
        if request.get("Action") == "Storage":
            # Reassemble JSON as dict for storage in object
            try:
                cluster_to_store = ClusterStoreRequest.from_eps_dict(request)
                response = self.store_cluster(cluster_to_store)
                if response:
                    socket.send_json({"result": "success", "cluster_id": response})
                else:
                    raise FailedProcException
            except FailedProcException as err:
                socket.send_json(
                    {"result": "failure", "cluster_id": None, "error": str(err)}
                )

        elif request.get("Action") == "Retrieval":
            try:
                retrieval_clusters = ClusterQueryFilter.from_eps_dict(request)
                response = self.retrieve_clusters(retrieval_clusters)
                socket.send_json(response)
            except Exception as err:
                socket.send_json(
                    {"result": "failure", "clusters": None, "error": str(err)}
                )

        elif request.get("Action") == "RecentRetrieval":
            try:
                recent_clusters = ClusterRecentQueryFilter.from_eps_dict(request)
                response = self.retrieve_recent_clusters(recent_clusters)
                socket.send_json(response)
            except Exception as err:
                socket.send_json(
                    {"result": "failure", "clusters": None, "error": str(err)}
                )

        elif request.get("Action") == "UpdateClassification":
            try:
                cluster_to_classify = ClassificationUpdateRequest.from_eps_dict(request)
                response = self.classify_cluster(cluster_to_classify)
                socket.send_json(response)
            except Exception as err:
                socket.send_json(
                    {"result": "failure", "error": str(err)}
                )

        elif request.get("Action") == "PagedRetrieval":
            try:
                paged_filter = ClusterPagedQueryFilter.from_eps_dict(request)
                response = self.paged_retrieve_clusters(paged_filter)
                socket.send_json(dataclasses.asdict(response))
            except Exception as err:
                socket.send_json(
                    {"result": "failure", "clusters": None, "error": str(err)}
                )

    def fits_event(self, request: dict, socket: zmq.Socket):
        """Processes a requested cluster event and calls storage or retrieval of cluster."""
        logger.info("Fits request received by EPS.")
        if request.get("Action") == "Storage":
            # Reassemble JSON as dict for storage in object
            try:
                fits = FitsStoreRequest.from_eps_dict(request)
                response = self.store_fits(fits)
                if response:
                    socket.send_json({"result": "success", "fits_id": response})
                else:
                    raise FailedProcException
            except FailedProcException as err:
                socket.send_json(
                    {"result": "failure", "fits_id": None, "error": str(err)}
                )

        elif request.get("Action") == "Retrieval":
            try:
                retrieval_fits = FitsQueryFilter.from_eps_dict(request)
                response = self.retrieve_fits(retrieval_fits)
                socket.send_json(response)
            except Exception as err:
                socket.send_json({"result": "failure", "fits": None, "error": str(err)})

        elif request.get("Action") == "Clusters":
            try:
                retrieval_fits = FitsQueryFilter.from_eps_dict(request)
                fits_ids = self.retrieve_fits(retrieval_fits)
                cluster_retrieval_ids = []
                for key in fits_ids["fits"]:
                    cluster_retrieval_ids.append(key["fits_id"])

                # Format cluster retrieval request to only contain fits_ids that we want to view
                retrieval_cluster_dict = {
                    "fits_list": cluster_retrieval_ids,
                }

                retrieval_clusters = ClusterQueryFilter.from_eps_dict(retrieval_cluster_dict)
                response = self.retrieve_clusters(retrieval_clusters)
                socket.send_json(response)
            except Exception as err:
                socket.send_json(
                    {"result": "failure", "clusters": None, "error": str(err)}
                )

    def store_fits(self, fits: FitsStoreRequest) -> int:
        """Uses the persistent EPS DB connection to call the stored procedure insert_fits on the database with the values from
        the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            filename = fits.filename
            date = fits.date
            minimum = fits.min
            maximum = fits.max
            exposure_time = fits.exposure_time
            proc_args = (filename, date, minimum, maximum, exposure_time, None)

            fits_id = cursor.callproc("insert_fits", proc_args)[-1]

            if fits_id and fits_id > 0:
                self.conn.commit()
                cursor.close()
                return fits_id
            else:
                self.conn.close()
                self.conn = None
                raise FailedProcException

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

    def store_cluster(self, cluster: ClusterStoreRequest) -> int:
        """Uses the persistent EPS DB connection to call the stored procedure insert_cluster on the database with the values
        from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            bounding_box = cluster.bounding_box or {}
            box_top = bounding_box.get("top")
            box_left = bounding_box.get("left")
            box_bottom = bounding_box.get("bottom")
            box_right = bounding_box.get("right")

            proc_args = (
                cluster.fits_id,
                cluster.hdu_id,
                box_top,
                box_left,
                box_bottom,
                box_right,
                cluster.data,
                cluster.total_energy,
                cluster.sigma_x,
                cluster.sigma_y,
                cluster.classification,
                None,  # null values for per model classifications
                None,
                None,
                cluster.total_pixels,
                None,
            )

            cluster_id = cursor.callproc("insert_cluster", proc_args)[-1]
            if cluster_id and cluster_id > 0:
                self.conn.commit()
                cursor.close()
                return cluster_id
            else:
                self.conn.close()
                self.conn = None
                raise FailedProcException

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

    def retrieve_fits(self, fits: FitsQueryFilter) -> dict:
        """Selects from the database all values from the fits table that match any and all values from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor(dictionary=True)

            filename = fits.filename
            fits_id = fits.fits_id
            date_start = str(fits.date_start) if fits.date_start else None
            date_end = str(fits.date_end) if fits.date_start else None
            date_range = _parse_date_filter({"start": date_start, "end": date_end})
            minimum = fits.minimum
            maximum = fits.maximum
            exposure_time = fits.exposure_time
            select_query = "SELECT * FROM fits_files"
            select_args = []
            select_argv = []
            if filename:
                select_args.append("fileName = %s")
                select_argv.append(filename)
            if fits_id:
                select_args.append("fitsID = %s")
                select_argv.append(fits_id)
            if date_range is not None:
                select_args.append("date BETWEEN %s AND %s")
                select_argv.extend(date_range)
            if minimum:
                select_args.append("min = %s")
                select_argv.append(minimum)
            if maximum:
                select_args.append("max = %s")
                select_argv.append(maximum)
            if exposure_time:
                select_args.append("exposureTime = %s")
                select_argv.append(exposure_time)

            if len(select_args) > 0:
                select_query += " WHERE " + " AND ".join(select_args)

            cursor.execute(select_query, tuple(select_argv))
            # saving results into a list of tuples
            results = cursor.fetchall()

            cursor.close()
            return self.process_retrieval_fits(results)

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

    def retrieve_clusters(self, clusters: ClusterQueryFilter) -> dict:
        """Selects from the database all values from the clusters table that match any and all values from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor(dictionary=True)
            hdu = clusters.hdu_id
            cluster_id = clusters.cluster_id
            date_start = str(clusters.date_start) if clusters.date_start else None
            date_end = str(clusters.date_end) if clusters.date_end else None
            date_range = _parse_date_filter({"start": date_start, "end": date_end})
            bounding_box = clusters.bounding_box
            fits_id = clusters.fits_id
            fits_list = clusters.fits_list
            sigmaX = clusters.min_sigma_x
            sigmaY = clusters.min_sigma_y
            total_energy = clusters.min_total_energy
            total_pixels = clusters.min_total_pixels
            classification = clusters.classification

            select_query = "SELECT clusters.*, fits_files.filename, fits_files.date FROM clusters INNER JOIN fits_files ON clusters.fitsFile = fits_files.fitsID"
            select_args = []
            select_argv = []
            if hdu:
                select_args.append("hdu_id = %s")
                select_argv.append(hdu)
            if bounding_box:
                select_args.extend(
                    ["box_top = %s", "box_left = %s", "box_bottom = %s", "box_right = %s"]
                )
                select_argv.extend(
                    [
                        bounding_box["top"],
                        bounding_box["left"],
                        bounding_box["bottom"],
                        bounding_box["right"],
                    ]
                )
            if date_range is not None:
                select_args.append("fits_files.date BETWEEN %s AND %s")
                select_argv.extend(date_range)
            if fits_id:
                select_args.append("fitsFile = %s")
                select_argv.append(fits_id)
            if fits_list:
                placeholder = ", ".join(["%s"] * len(fits_list))
                select_args.append(f"fitsFile in ({placeholder})")
                select_argv.extend(fits_list)
            if cluster_id:
                select_args.append("clusterId = %s")
                select_argv.append(cluster_id)
            if sigmaX:
                select_args.append("sigmaX >= %s")
                select_argv.append(sigmaX)
            if sigmaY:
                select_args.append("sigmaY >= %s")
                select_argv.append(sigmaY)
            if total_energy:
                select_args.append("totalEnergy >= %s")
                select_argv.append(total_energy)
            if total_pixels:
                select_args.append("pixelCount >= %s")
                select_argv.append(total_pixels)
            if classification:
                select_args.append("classification = %s")
                select_argv.append(classification)

            if len(select_args) > 0:
                select_query += " WHERE " + " AND ".join(select_args)

            select_query += " LIMIT 2000"

            cursor.execute(select_query, tuple(select_argv))
            # saving results into a list of tuples
            results = cursor.fetchall()  # Temporarily limit result set size to avoid a crash in macOS

            cursor.close()
            return self.process_retrieval_clusters(results)

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

    def classify_cluster(self, cluster: ClassificationUpdateRequest) -> dict:
        """Executes the insert_classifications stored procedure in the database based on the EPS
            UpdateClassification request.
        """
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            cluster_id = cluster.cluster_id
            classification = cluster.classification
            proc_args = (classification, cluster_id, None)
            rows_updated = cursor.callproc("insert_classifications", proc_args)[-1]

            if rows_updated is not None and rows_updated > 0:
                self.conn.commit()
                cursor.close()
                return {"result": "success", "updated": rows_updated}
            elif rows_updated == 0:
                self.conn.commit()
                cursor.close()
                return {"result": "failure", "error": "No clusters were updated, incorrect ID or classification."}
            else:
                self.conn.close()
                self.conn = None
                raise FailedProcException

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

    def retrieve_recent_clusters(self, recent_clusters: ClusterRecentQueryFilter) -> dict:
        """Selects the newest clusters ordered by FITS date, paginated.

        Uses the ``limit`` and ``offset`` stored in
        ``self.retrieval_recent_clusters``. Reuses
        ``process_retrieval_clusters`` to shape the response.
        """
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor(dictionary=True)

            limit = int(recent_clusters.limit or 0)
            offset = int(recent_clusters.offset or 0)

            select_query = (
                "SELECT clusters.*, fits_files.filename, fits_files.date "
                "FROM clusters INNER JOIN fits_files "
                "ON clusters.fitsFile = fits_files.fitsID "
                "ORDER BY fits_files.date DESC "
                "LIMIT %s OFFSET %s"
            )
            cursor.execute(select_query, (limit, offset))
            results = cursor.fetchall()

            cursor.close()
            return self.process_retrieval_clusters(results)

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

    def paged_retrieve_clusters(self, paged_filter: ClusterPagedQueryFilter) -> PagedRetrieveClustersResponse:
        """Selects clusters matching ``paged_filter`` with bounded pagination.

        Defaults and caps the effective ``limit`` from
        ``eps:retrieval_limit_default`` / ``eps:retrieval_limit_max`` so an
        unbounded or excessive client request cannot return the entire
        table. Delegates the query and formatting to
        ``PagedClusterRetrieval.paged_retrieve_clusters``.
        """
        if not self.conn:
            self.conn = self.db_connect()
        default_limit = int(self.config.get("eps:retrieval_limit_default", 500))
        max_limit = int(self.config.get("eps:retrieval_limit_max", 2000))
        return _paged_retrieve_clusters(self.conn, paged_filter, default_limit, max_limit)

    def process_retrieval_fits(self, results) -> dict:
        """Takes the results from a fits retrieval SELECT statement and formats the EPS response into JSON.

        args:
            results: list of results from the retrieve_fits function, collection of mySQL fetches
        """
        # If a string was returned as the results from the fits_retrieval function, it was the mySQL error.
        if isinstance(results, str):
            response = {"result": "failure", "fits": None, "error": results}
            return response
        fits_list = []
        for result in results:
            # Dictionary return from a select statement will be in the format:
            # `fitsID`, `fileName`, `date` , `min`, `max`, `exposureTime`,
            fits_list.append(
                {
                    "fits_id": result["fitsID"],
                    "filename": result["fileName"],
                    "date": str(result["date"]),
                    "min": result["min"],
                    "max": result["max"],
                    "exposure_time": result["exposureTime"],
                }
            )
        response = {"result": "success", "fits": fits_list}
        return response

    def process_retrieval_clusters(self, results) -> dict:
        """Takes the results from a fits retrieval SELECT statement and formats the EPS response into JSON.

        args:
            results: list of results from the retrieve_fits function, collection of mySQL fetches
        """
        if type(results) is str:
            response = {"result": "failure", "clusters": None, "error": results}
            return response
        clusters_list = []
        for result in results:
            # Results return as a list of dictionaries
            clusters_list.append(
                {
                    "fits_id": result["fitsFile"],
                    "cluster_id": result["clusterID"],
                    "hdu_id": result["hdu_id"],
                    "bounding_box": {
                        "top": result["box_top"],
                        "left": result["box_left"],
                        "bottom": result["box_bottom"],
                        "right": result["box_right"],
                    },
                    "data": None,
                    "total_energy": result["totalEnergy"],
                    "sigmaX": result["sigmaX"],
                    "sigmaY": result["sigmaY"],
                    "classification": result["classification"],
                    "total_pixels": result["pixelCount"],
                    "filename": result["filename"],
                    "date": str(result["date"])
                }
            )
        response = {"result": "success", "clusters": clusters_list}
        return response
