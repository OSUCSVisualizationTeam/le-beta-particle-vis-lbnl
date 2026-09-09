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


class ZMQBasedClassifierServer():
    """ClassifierService class with a ZMQ based endpoint for retrieving clusters
        and returning classifications."""

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
        try:
            classifier_socket, command_socket, socket_poller = self._bind_sockets(context)
        except Exception:
            context.term()
            raise

        classifier_is_active = True
        try:
            while True:
                try:
                    # timeout can be adjusted for performance
                    sockets = dict(socket_poller.poll(timeout=100))
                    if classifier_socket in sockets:
                        self._handle_classifier_message(classifier_socket, classifier_is_active)
                    if command_socket in sockets:
                        classifier_is_active, should_stop = self._handle_command_message(
                            command_socket, classifier_is_active
                        )
                        if should_stop:
                            break
                except zmq.ZMQError as err:
                    print(f"ERROR: {str(err)}")
        finally:
            classifier_socket.close()
            command_socket.close()
            context.term()

    def _bind_sockets(self, context: "zmq.Context"):
        """Creates the classifier and command REP sockets, binds them, and registers a poller.

        Closes any socket already created before re-raising, so a bind failure never leaks a
        partially-set-up socket.
        """
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
            return classifier_socket, command_socket, socket_poller
        except Exception:
            if classifier_socket:
                classifier_socket.close()
            if command_socket:
                command_socket.close()
            raise

    def _handle_classifier_message(self, classifier_socket: "zmq.Socket", classifier_is_active: bool) -> None:
        """Handles one pending request on the classifier socket."""
        request = classifier_socket.recv_json()
        request_dict = ClassificationRequest.from_classifier_dict(request)
        if not classifier_is_active:
            classifier_socket.send_json({"Error": "Server is stopped."})
        else:
            self.classify_event(request_dict, classifier_socket)

    def _handle_command_message(self, command_socket: "zmq.Socket", classifier_is_active: bool):
        """Handles one pending request on the command socket.

        Returns the (possibly updated) ``classifier_is_active`` flag and whether the server
        loop should stop.
        """
        request = command_socket.recv_json()
        if request.get("Command") == "Kill":
            command_socket.send_json({"Action": "Killed"})
            return classifier_is_active, True
        elif request.get("Command") == "Stop":
            command_socket.send_json({"Action": "Server stopped"})
            return False, False
        elif request.get("Command") == "Start" and not classifier_is_active:
            command_socket.send_json({"Action": "Server started"})
            return True, False
        else:
            command_socket.send_json({"Error": "Invalid request"})
            return classifier_is_active, False

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
                "results": [ZMQBasedClassifierServer._result_to_dict(r) for r in batch.results],
            },
            "total": batch.total,
            "failed": batch.failed,
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
