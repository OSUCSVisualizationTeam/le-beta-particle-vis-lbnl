import mysql.connector
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
import os
import zmq
import numpy as np
import logging

logger = logging.getLogger(__name__)


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

        # Initialize storage and retrieval dictionaries to avoid unbound local errors
        self.fits_to_store = {
            "filename": None,
            "date": None,
            "minimum": None,
            "maximum": None,
            "exposure_time": None,
        }
        self.retrieval_fits = {
            "filename": None,
            "fits_id": None,
            "date": None,
            "minimum": None,
            "maximum": None,
            "exposure_time": None,
        }
        self.cluster_to_store = {
            "data": None,
            "bounding_box": None,
            "hdu_id": None,
            "sigmaX": None,
            "sigmaY": None,
            "total_energy": None,
            "total_pixels": None,
            "fits_id": None,
            "classification": None,
        }
        self.retrieval_clusters = {
            "data": None,
            "cluster_id": None,
            "bounding_box": None,
            "date": None,
            "hdu_id": None,
            "sigmaX": None,
            "sigmaY": None,
            "total_energy": None,
            "total_pixels": None,
            "fits_id": None,
            "classification": None,
        }

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
            fits_socket.bind(
                self.config.get("eps:fits_ipc")
            )  # EPC***.ipc will be the file created for IPC, becomes a pipe on windows
            cluster_socket = context_manager.socket(zmq.REP)
            cluster_socket.bind(self.config.get("eps:cluster_ipc"))
            command_socket = context_manager.socket(zmq.REP)
            command_socket.bind(self.config.get("eps:command_ipc"))

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
                        if EPS_is_active == False:
                            cluster_socket.send_json({"Error": "Server is stopped."})
                        else:
                            self.cluster_event(request, cluster_socket)

                    if fits_socket in sockets:
                        request = fits_socket.recv_json()
                        if EPS_is_active == False:
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
                self.cluster_to_store = {
                    "data": request.get("data"),
                    "bounding_box": request.get("bounding_box"),
                    "hdu_id": request.get("hdu_id"),
                    "sigmaX": request.get("sigmaX"),
                    "sigmaY": request.get("sigmaY"),
                    "total_energy": request.get("total_energy"),
                    "total_pixels": request.get("total_pixels"),
                    "fits_id": request.get("fits_id"),
                    "classification": request.get("classification"),
                }
                response = self.store_cluster()
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
                self.retrieval_clusters = {
                    "data": request.get("data"),
                    "cluster_id": request.get("cluster_id"),
                    "bounding_box": request.get("bounding_box"),
                    "date": request.get("date"),
                    "hdu_id": request.get("hdu_id"),
                    "sigmaX": request.get("sigmaX"),
                    "sigmaY": request.get("sigmaY"),
                    "total_energy": request.get("total_energy"),
                    "total_pixels": request.get("total_pixels"),
                    "fits_id": request.get("fits_id"),
                    "classification": request.get("classification"),
                }
                response = self.retrieve_clusters()
                socket.send_json(response)
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
                self.fits_to_store = {
                    "filename": request.get("filename"),
                    "date": request.get("date"),
                    "minimum": request.get("minimum"),
                    "maximum": request.get("maximum"),
                    "exposure_time": request.get("exposure_time"),
                }
                response = self.store_fits()
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
                self.retrieval_fits = {
                    "filename": request.get("filename"),
                    "fits_id": request.get("fits_id"),
                    "date": request.get("date"),
                    "minimum": request.get("minimum"),
                    "maximum": request.get("maximum"),
                    "exposure_time": request.get("exposure_time"),
                }
                response = self.retrieve_fits()
                socket.send_json(response)
            except Exception as err:
                socket.send_json({"result": "failure", "fits": None, "error": str(err)})

        elif request.get("Action") == "Clusters":
            try:
                self.retrieval_fits = {
                    "filename": request.get("filename"),
                    "fits_id": request.get("fits_id"),
                    "date": request.get("date"),
                    "minimum": request.get("minimum"),
                    "maximum": request.get("maximum"),
                    "exposure_time": request.get("exposure_time"),
                }
                fits_ids = self.retrieve_fits()
                cluster_retrieval_ids = []
                for key in fits_ids["fits"]:
                    cluster_retrieval_ids.append(key["fits_id"])

                # Format cluster retrieval request to only contain fits_ids that we want to view
                self.retrieval_clusters = {
                    "data": None,
                    "cluster_id": None,
                    "bounding_box": None,
                    "hdu_id": None,
                    "sigmaX": None,
                    "sigmaY": None,
                    "total_energy": None,
                    "total_pixels": None,
                    "fits_id": cluster_retrieval_ids,
                    "classification": None,
                }

                response = self.retrieve_clusters()
                socket.send_json(response)
            except Exception as err:
                socket.send_json(
                    {"result": "failure", "clusters": None, "error": str(err)}
                )

    def store_fits(self) -> int:
        """Uses the persistent EPS DB connection to call the stored procedure insert_fits on the database with the values from
        the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            filename = self.fits_to_store["filename"]
            date = self.fits_to_store["date"]
            minimum = self.fits_to_store["minimum"]
            maximum = self.fits_to_store["maximum"]
            exposure_time = self.fits_to_store["exposure_time"]
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

    def store_cluster(self) -> int:
        """Uses the persistent EPS DB connection to call the stored procedure insert_cluster on the database with the values
        from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            bounding_box = self.cluster_to_store.get("bounding_box") or {}
            box_top = bounding_box.get("top")
            box_left = bounding_box.get("left")
            box_bottom = bounding_box.get("bottom")
            box_right = bounding_box.get("right")

            proc_args = (
                self.cluster_to_store["fits_id"],
                self.cluster_to_store["hdu_id"],
                box_top,
                box_left,
                box_bottom,
                box_right,
                self.cluster_to_store["data"],
                self.cluster_to_store["total_energy"],
                self.cluster_to_store["sigmaX"],
                self.cluster_to_store["sigmaY"],
                self.cluster_to_store["classification"],
                self.cluster_to_store["total_pixels"],
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

    def retrieve_fits(self) -> dict:
        """Selects from the database all values from the fits table that match any and all values from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()

            filename = self.retrieval_fits["filename"]
            fits_id = self.retrieval_fits["fits_id"]
            date = self.retrieval_fits["date"]
            minimum = self.retrieval_fits["minimum"]
            maximum = self.retrieval_fits["maximum"]
            exposure_time = self.retrieval_fits["exposure_time"]
            select_query = "SELECT * FROM fits_files"
            select_args = []
            select_argv = []
            if filename:
                select_args.append("filename = %s")
                select_argv.append(filename)
            if fits_id:
                select_args.append("fitsID = %s")
                select_argv.append(fits_id)
            if date:
                if date.get("start") and date.get("end"):
                    select_args.append("date BETWEEN %s AND %s")
                    select_argv.extend([date["start"], date["end"]])
                else:
                    select_args.append("date = %s")
                    select_argv.append(date)
            if minimum:
                select_args.append("minimum = %s")
                select_argv.append(minimum)
            if maximum:
                select_args.append("maximum = %s")
                select_argv.append(maximum)
            if exposure_time:
                select_args.append("exposure_time = %s")
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

    def retrieve_clusters(self) -> dict:
        """Selects from the database all values from the clusters table that match any and all values from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()

            data = self.retrieval_clusters["data"]
            hdu = self.retrieval_clusters["hdu_id"]
            cluster_id = self.retrieval_clusters["cluster_id"]
            date = self.retrieval_clusters["date"]
            bounding_box = self.retrieval_clusters["bounding_box"]
            fits_id = self.retrieval_clusters["fits_id"]
            sigmaX = self.retrieval_clusters["sigmaX"]
            sigmaY = self.retrieval_clusters["sigmaY"]
            total_energy = self.retrieval_clusters["total_energy"]
            total_pixels = self.retrieval_clusters["total_pixels"]
            classification = self.retrieval_clusters["classification"]

            select_query = "SELECT * FROM clusters"
            select_args = []
            select_argv = []
            if data:
                select_args.append("data = %s")
                select_argv.append(data)
            if hdu:
                select_args.append("hdu_id = %s")
                select_argv.append(hdu)
            if bounding_box:
                select_args.extend(
                    ["top = %s", "left = %s", "bottom = %s", "right = %s"]
                )
                select_argv.extend(
                    [
                        bounding_box["top"],
                        bounding_box["left"],
                        bounding_box["bottom"],
                        bounding_box["right"],
                    ]
                )
            if date:
                if date.get("start") and date.get("end"):
                    select_query += " INNER JOIN fits_files ON clusters.fitsFile = fits_files.fitsID"
                    select_args.append("fits_files.date BETWEEN %s AND %s")
                    select_argv.extend([date["start"], date["end"]])
            if fits_id:
                if isinstance(fits_id, list):
                    # If searching multiple fits files, set up parameters and append tuples to arg values
                    placeholder = ", ".join(["%s"] * len(fits_id))
                    select_args.append(f"fitsFile in {placeholder}")
                    select_argv.append(tuple(fits_id))
                else:
                    select_args.append("fitsFile = %s")
                    select_argv.append(fits_id)
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

            cursor.execute(select_query, tuple(select_argv))
            # saving results into a list of tuples
            results = cursor.fetchall()

            cursor.close()
            return self.process_retrieval_clusters(results)

        except mysql.connector.Error as err:
            logger.warning(f"Could not connect: {str(err)}")

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
            # Tuple return from a select statement will be in the order:
            # `fitsID`, `fileName`, `date` , `min`, `max`, `exposureTime`,
            fits_list.append(
                {
                    "fits_id": result[0],
                    "filename": result[1],
                    "date": str(result[2]),
                    "min": result[3],
                    "max": result[4],
                    "exposure_time": result[5],
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
            # Tuple return from a select statement will be in the order:
            # `fitsFile`, `clusterID`, `hdu_id`, bounding_box, `data`, `totalEnergy`, `sigmaX`, `sigmaY`, `classification`, `pixelCount`,
            clusters_list.append(
                {
                    "fits_id": result[0],
                    "cluster_id": result[1],
                    "hdu_id": result[2],
                    "bounding_box": {
                        "top": result[3],
                        "left": result[4],
                        "bottom": result[5],
                        "right": result[6],
                    },
                    "data": None,
                    "total_energy": result[8],
                    "sigmaX": result[9],
                    "sigmaY": result[10],
                    "classification": result[11],
                    "total_pixels": result[12],
                }
            )
        response = {"result": "success", "clusters": clusters_list}
        return response
