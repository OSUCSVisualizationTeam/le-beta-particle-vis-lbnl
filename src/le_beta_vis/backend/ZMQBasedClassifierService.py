from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable

from coverage import data
from le_beta_vis.common import (
    Cluster,
    BoundingBox
)
from le_beta_vis.common.ParticleType import (
    ParticleType
)
from le_beta_vis.common.ClassifierService import (
    ClassificationScore,
    ClassificationResult,
    ClassificationBatchResult,
    ClassifierService,
    CompletionCallback,
    ErrorCallback
)
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
import zmq

def ZMQBasedClassifierService(ClassifierService):
    """ClassifierService class with a ZMQ based endpoint for retrieving clusters
        and returning classifications.
    """
    def __init___(self):
        self.config = YAMLBackedConfigurationService()
        self._on_error_callbacks = ErrorCallback
        self._on_completion_callback = CompletionCallback
        self.initialize_server()

    def initialize_server(self):
        """Initializes configured ZMQ socket and context for ZMQ based classifier service."""
        context = zmq.Context()
        classifier_socket = None
        command_socket = None
        try:
            classifier_socket = context.socket(zmq.REP)
            classifier_socket.bind(
                self.config.get("classifier:classifier_ipc")
            )  # EPC***.ipc will be the file created for IPC, becomes a pipe on windows
            socket_poller = zmq.Poller()
            socket_poller.register(classifier_socket, zmq.POLLIN)
            socket_poller.register(command_socket, zmq.POLLIN)
            classifier_is_active = True
            while True:
                try:
                    # timeout can be adjusted for performance
                    sockets = dict(socket_poller.poll(timeout=100))
                    if classifier_socket in sockets:
                        request = classifier_socket.recv_json()
                        if classifier_is_active == False:
                            classifier_socket.send_json({"Error": "Server is stopped."})
                        else:
                            self.classify_event(request, classifier_socket)
                    if command_socket in sockets:
                        request = command_socket.recv_json()
                        if request.get("Command") == "Kill":
                            command_socket.send_json({"Action": "Killed"})
                            break
                        elif request.get("Command") == "Stop":
                            classifier_is_active = False
                            command_socket.send_json({"Action": "Server stopped"})
                        elif request.get("Command") == "Start" and not classifier_is_active:
                            classifier_is_active = True
                            command_socket.send_json({"Action": "Server started"})
                        else:
                            command_socket.send_json({"Error": "Invalid request"})
                except zmq.ZMQError as err:
                    print(f"ERROR: {str(err)}")
        finally:
            if classifier_socket:
                classifier_socket.close()
            if command_socket:
                command_socket.close()
            context.term()

    def classify_event(
        self,
        request: dict,
        socket: zmq.Socket
    ) -> None:
        """Parses cluster list and routes a classification event to the appropriate model classification handler."""
        model = request.get("Model", None)
        if model:
            clusters = []
            for cluster in request.get("Clusters"):
                bounding_box = cluster.get("bounding_box")
                clusters.append(
                    Cluster(
                        boundingBox=BoundingBox(
                            bounding_box.get("top"),
                            bounding_box.get("left"),
                            bounding_box.get("bottom"),
                            bounding_box.get("right")
                        ),
                        data=cluster.get("data"),
                        sigmaX=cluster.get("sigmaX"),
                        sigmaY=cluster.get("sigmaY"),
                        energy=cluster.get("total_energy"),
                        pixelCount=cluster.get("total_pixels"),
                        clusterId = cluster.get("cluster_id")
                    ))

            match model:
                case "NRG":
                    self.classify_nrg(clusters, self._on_completion_callback, self._on_error_callback)
                case "CNN":
                    self.classify_cnn(clusters, self._on_completion_callback, self._on_error_callback)
                case "BDT":
                    self.classify_bdt(clusters, self._on_completion_callback, self._on_error_callback)
                case _:
                    socket.send_json({"result": "failure", "error": "Specified model is not supported."})
        else:
            socket.send_json({"result": "failure", "error": "No model was specified."})

    def classify_cnn(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        raise NotImplementedError

    def classify_nrg(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        raise NotImplementedError

    def classify_bdt(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        raise NotImplementedError
