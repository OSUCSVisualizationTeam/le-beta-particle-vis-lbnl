import mysql.connector
from le_beta_vis.common.RedisBackedConfigurationService import RedisBackedConfigurationService
import os
import zmq
import numpy as np


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
                        "sigmaX": request["sigmaX"],
                        "sigmaY": request["sigmaY"],
                        "total_energy": request["total_energy"],
                        "total_pixels": request["total_pixels"],
                        "fits_id": request["fits_id"],
                        "cnn_classification": request["cnn_classification"],
                        "nrg_classification": request["nrg_classification"],
                        "bdt_classification": request["bdt_classification"]
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
                        "sigmaX": request["sigmaX"],
                        "sigmaY": request["sigmaY"],
                        "total_energy": request["total_energy"],
                        "total_pixels": request["total_pixels"],
                        "fits_id": request["fits_id"],
                        "cnn_classification": request["cnn_classification"],
                        "nrg_classification": request["nrg_classification"],
                        "bdt_classification": request["bdt_classification"]
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
        raise NotImplementedError
    
    def store_clusters(self) -> int:
        raise NotImplementedError
    
    def retrieve_fits(self) -> dict:
        raise NotImplementedError
    
    def retrieve_clusters(self) -> dict:
        raise NotImplementedError
