from typing import Iterable
from le_beta_vis.common.ClassifierDataClasses import (
    ClassificationRequest,
    ClassificationRequestCluster
)
from le_beta_vis.common.ClassifierService import (
    ClassifierService,
)
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
import zmq

class ZMQBasedClassifierService():
    """ClassifierService class with a ZMQ based endpoint for retrieving clusters
        and returning classifications.
    """
    def __init__(
            self, 
            config: YAMLBackedConfigurationService,
            classifier: ClassifierService,
            auto_start: bool = True,
                  ):
        self.config = config
        self.classifier_service = classifier
        if auto_start:
            self.initialize_server()

    def initialize_server(self):
        """Initializes configured ZMQ socket and context for ZMQ based classifier service."""
        context = zmq.Context()
        classifier_socket = None
        command_socket = None
        try:
            classifier_socket = context.socket(zmq.REP)
            command_socket = context.socket(zmq.REP)
            classifier_socket.bind(
                self.config.get("classifier:classifier_ipc")
            )  # EPC***.ipc will be the file created for IPC, becomes a pipe on windows
            command_socket.bind(
                self.config.get("classifier:command_ipc")
            )
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
                        request_dict = ClassificationRequest.from_classifier_dict(request)
                        if classifier_is_active == False:
                            classifier_socket.send_json({"Error": "Server is stopped."})
                        else:
                            self.classify_event(request_dict, classifier_socket)
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
        request: ClassificationRequest,
        socket: zmq.Socket,
    ) -> None:
        """Parses cluster list and routes a classification event to the appropriate model classification handler."""
        model = (request.model or "").strip().upper()
        if not model:
            socket.send_json({"result": "failure", "error": "No model was specified."})
            return

        clusters = self._normalize_clusters(request.clusters)

        def on_complete(batch) -> None:
            socket.send_json(self._batch_to_dict(batch))

        def on_error(err: Exception) -> None:
            socket.send_json({"result": "failure", "error": str(err)})

        match model:
            case "NRG":
                self.classifier_service.classify_nrg(
                    clusters, on_complete, on_error
                )
            case "CNN":
                self.classifier_service.classify_cnn(
                    clusters, on_complete, on_error
                )
            case "BDT":
                self.classifier_service.classify_bdt(
                    clusters, on_complete, on_error
                )
            case _:
                socket.send_json({
                    "result": "failure",
                    "error": "Specified model is not supported.",
                })

    @staticmethod
    def _normalize_clusters(
        clusters: Iterable[ClassificationRequestCluster | dict],
    ) -> list[ClassificationRequestCluster]:
        normalized: list[ClassificationRequestCluster] = []
        for cluster in clusters:
            if isinstance(cluster, ClassificationRequestCluster):
                normalized.append(cluster)
            elif isinstance(cluster, dict):
                normalized.append(
                    ClassificationRequestCluster.from_cluster_dict(cluster)
                )
        return normalized

    @staticmethod
    def _batch_to_dict(batch) -> dict:
        return {
            "result": "success",
            "classifications": {
                "results": [ZMQBasedClassifierService._result_to_dict(r) for r in batch.results],
                "total": batch.total,
                "failed": batch.failed,
            },
        }

    @staticmethod
    def _result_to_dict(result) -> dict:
        score = None
        if result.score:
            score = {
                "particle_type": result.score.particle_type.name,
                "confidence": result.score.confidence,
            }
        return {
            "cluster_id": result.cluster_id,
            "model": result.model,
            "score": score,
        }