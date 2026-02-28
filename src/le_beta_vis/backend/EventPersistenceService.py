import mysql.connector
from le_beta_vis.common.RedisBackedConfigurationService import RedisBackedConfigurationService
import os
import zmq
import numpy as np
from dotenv import load_dotenv

load_dotenv()

class FailedProcException(Exception):
    """
    Subclassed exception to handle failed procedure calls in the database
    """
    def __init__(self, message="There was an issue running the stored procedure."):
        super().__init__(message)
        self.message = message

class EventPersistence():
    """
    This class defines the EventPersistenceService that interfaces with the database.
    It is responsible for the storage and retrieval of FITS and cluster information
    """
    def __init__(self):
        self.config = RedisBackedConfigurationService()
        self.db_host="localhost"
        self.db_user=os.environ.get("DB_USER")
        self.db_password=os.environ.get("DB_PASS")
        self.database=os.environ.get("DB_NAME")
        self.conn = None
        self.db_connect()   # connect to DB before listening loop
        self.initialize_server()

    def initialize_server(self):
        """Initialize the zmq server endpoint socket to listen for requests"""
        context_manager = zmq.Context()
        fits_socket = context_manager.socket(zmq.REP)
        fits_socket.bind("ipc:///tmp/EPCFits.ipc")    #EPC***.ipc will be the file created for IPC, becomes a pipe on windows
        cluster_socket = context_manager.socket(zmq.REP)
        cluster_socket.bind("ipc:///tmp/EPCCluster.ipc")
        command_socket = context_manager.socket(zmq.REP)
        command_socket.bind("ipc:///tmp/EPCCommand.ipc")

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
                        self.cluster_event(request)

                if fits_socket in sockets:
                    request = fits_socket.recv_json()
                    if EPS_is_active == False:
                        cluster_socket.send_json({"Error": "Server is stopped."})
                    else:
                        self.fits_event(request, fits_socket)

                if command_socket in sockets:
                    request = command_socket.recv_json()
                    if request.get("Command") == "Kill":
                        print("EPS received kill command.")
                        break
                    if request.get("Command") == "Stop":
                        EPS_is_active = False
                        command_socket.send_json({"Action": "Server stopped"})
                    if request.get("Command") == "Start" and EPS_is_active == False:
                        EPS_is_active = True
                        command_socket.send_json({"Action": "Server started"})
                    else:
                        command_socket.send_json({"Arror": "Invalid request"})

            except zmq.ZMQError as err:
                print(f"ERROR: {err}")

        cluster_socket.close()
        fits_socket.close()
        command_socket.close()
        context_manager.term()

    def db_connect(self):
        """
        Opens a connection to the database with the values from the configuration
        """
        try:
            conn = mysql.connector.connect(
                    host=self.db_host,
                    user=self.db_user,
                    password=self.db_password,
                    database=self.database
            )
            return conn
        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")

    def cluster_event(self, request: dict, socket: zmq.Socket):
        """Processes a requested cluster event and calls storage or retrieval of cluster."""
        if request.get("Action") == "Storage":
            # Reassemble JSON as dict for storage in object
            try:
                self.cluster_to_store = {
                        "data": np.array(request["data"]),
                        "bounding_box": request["bounding_box"],
                        "hdu_id": request["hdu_id"],
                        "sigmaX": request["sigmaX"],
                        "sigmaY": request["sigmaY"],
                        "total_energy": request["total_energy"],
                        "total_pixels": request["total_pixels"],
                        "fits_id": request["fits_id"],
                        "classification": request["classification"]
                }
                response = self.store_cluster()
                socket.send_json(response)
            except KeyError as err:
                socket.send_json({"result": "failure", "cluster_id": None, "error": err})

        elif request.get("Action") == "Retrieval":
            try:
                self.retrieval_clusters = {
                        "data": np.array(request["data"]),
                        "cluster_id": request["cluster_id"],
                        "hdu_id": request["hdu_id"],
                        "bounding_box": request["bounding_box"],
                        "sigmaX": request["sigmaX"],
                        "sigmaY": request["sigmaY"],
                        "total_energy": request["total_energy"],
                        "total_pixels": request["total_pixels"],
                        "fits_id": request["fits_id"],
                        "classification": request["classification"]
                }
                response = self.retrieve_clusters()
                socket.send_json(response)
            except KeyError as err:
                socket.send_json({"result": "failure", "clusters": None, "error": err})

    def fits_event(self, request: dict, socket: zmq.Socket):
        """Processes a requested cluster event and calls storage or retrieval of cluster."""
        if request.get("Action") == "Storage":
            # Reassemble JSON as dict for storage in object
            try:
                self.fits_to_store = {
                        "filename": request["filename"],
                        "date": request["date"],
                        "minimum": request["minimum"],
                        "maximum": request["maximum"],
                        "exposure_time": request["exposure_time"]
                    }
                response = self.store_fits()
                socket.send_json(response)
            except KeyError as err:
                socket.send_json({"result": "failure", "fits_id": None, "error": err})

        elif request.get("Action") == "Retrieval":
            try:
                self.retrieval_fits = {
                        "filename": request["filename"],
                        "fits_id": request["fits_id"],
                        "date": request["date"],
                        "minimum": request["minimum"],
                        "maximum": request["maximum"],
                        "exposure_time": request["exposure_time"]
                    }
                response = self.retrieve_fits()
                socket.send_json(response)
            except KeyError as err:
                socket.send_json({"result": "failure", "fits": None, "error": err})

    def store_fits(self) -> int:
        """Uses the persistent EPS DB connection to call the stored procedure insert_fits on the database
            with the values from the request.
        """
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            filename = self.fits_to_store["filename"]
            date = self.fits_to_store["date"]
            minimum = self.fits_to_store["minimum"]
            maximum = self.fits_to_store["maximum"]
            exposure_time = self.fits_to_store["exposure_time"]
            proc_args = (filename, date, minimum, maximum, exposure_time, (0, 'INT'))
            cursor.callproc("insert_fits", proc_args)

            for result in cursor.stored_results():
                id = result.fetchone()[0]
                if id > 0:
                    fits_id = id
                else:
                    self.conn.close()
                    self.conn = None
                    raise FailedProcException

            # Commit results and close connection
            self.conn.commit()
            cursor.close()

            return fits_id

        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")

    def store_cluster(self) -> int:
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()
            proc_args = (self.cluster_to_store["fits_id"], self.cluster_to_store["data"],
                         self.cluster_to_store["hdu_id"],
                         self.cluster_to_store["bounding_box"].top, self.cluster_to_store["bounding_box"].left,
                         self.cluster_to_store["bounding_box"].bottom, self.cluster_to_store["bounding_box"].right,
                         self.cluster_to_store["total_energy"],
                         self.cluster_to_store["sigmaX"], self.cluster_to_store["sigmaY"],
                         self.cluster_to_store["classification"],
                         self.cluster_to_store["total_pixels"] ,(0, 'INT'))
            cursor.callproc("insert_cluster", proc_args)

            for result in cursor.stored_results():
                id = result.fetchone()[0]
                if id > 0:
                    cluster_id = id
                else:
                    self.conn.close()
                    self.conn = None
                    raise FailedProcException

            # Commit results and close connection
            self.conn.commit()
            cursor.close()

            return cluster_id

        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")
            return err

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

            select_query += "WHERE " + " AND ".join(select_args)

            cursor.execute(select_query, tuple(select_argv))
                # saving results into a list of tuples
            results = cursor.fetchall()

            cursor.close()
            return self.process_retrieval_fits(results)

        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")
            return err

    def retrieve_clusters(self) -> dict:
        """Selects from the database all values from the clusters table that match any and all values from the request."""
        try:
            if not self.conn:
                self.conn = self.db_connect()
            cursor = self.conn.cursor()

            data = self.retrieval_clusters["data"]
            hdu = self.retrieval_clusters["hdu_id"]
            cluster_id = self.retrieval_clusters["cluster_id"]
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
                select_args.append("hduID = %s")
                select_argv.append(hdu)
            if bounding_box:
                select_args.extend(["top = %s", "left = %s", "bottom = %s", "right = %s"])
                select_argv.extend([bounding_box.top, bounding_box.left, bounding_box.bottom, bounding_box.right])
            if fits_id:
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

            select_query += "WHERE " + " AND ".join(select_args)

            cursor.execute(select_query, tuple(select_argv))
                # saving results into a list of tuples
            results = cursor.fetchall()

            cursor.close()
            return self.process_retrieval_clusters(results)

        except mysql.connector.Error as err:
            print(f"Could not connect: {err}")
            return err

    def process_retrieval_fits(self, results) -> dict:
        """Takes the results from a fits retrieval SELECT statement and formats the EPS response into JSON

            args:
                results: list of results from the retrieve_fits function, collection of mySQL fetches
        """
        # If a string was returned as the results from the fits_retrieval function, it was the mySQL error.
        if type(results) == str:
            response = {
                "result": "failure",
                "fits": None,
                "error": results
            }
            return response
        fits_list = []
        for result in results:
        # Tuple return from a select statement will be in the order:
        # `fitsID`, `fileName`, `date` , `min`, `max`, `exposureTime`,
            fits_list.append({
                "fits_id": result[0],
                "filename": result[1],
                "date": result[2],
                "min": result[3],
                "max": result[4],
                "exposure_time": result[5]
            })
        response = {
            "result": "success",
            "fits": fits_list
        }
        return response

    def process_retrieval_clusters(self, results) -> dict:
        """Takes the results from a fits retrieval SELECT statement and formats the EPS response into JSON

            args:
                results: list of results from the retrieve_fits function, collection of mySQL fetches
        """
        if type(results) == str:
            response = {
                "result": "failure",
                "clusters": None,
                "error": results
            }
            return response
        clusters_list = []
        for result in results:
        # Tuple return from a select statement will be in the order:
        # `fitsFile`, `hdu_id`, `clusterID`, `data`, `totalEnergy`, `sigmaX`, `sigmaY`, `classification`, `pixelCount`,
            clusters_list.append({
                "fits_id": result[0],
                "hdu_id": result[1],
                "cluster_id": result[2],
                "data": result[3],
                "total_energy": result[4],
                "sigmaX": result[5],
                "sigmaY": result[6],
                "classification": result[7],
                "total_pixels": result[8]
            })
        response = {
            "result": "success",
            "clusters": clusters_list
        }
        return response
