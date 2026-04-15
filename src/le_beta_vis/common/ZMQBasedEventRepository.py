"""ZMQ-backed EventRepository that talks to Troy's EPS over IPC sockets.

Uses a fresh ``zmq.REQ`` socket per request to avoid REQ/REP state
machine issues on timeout.  All methods are safe to call when the EPS
is down — they return empty/default values and log warnings.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import threading

import numpy as np
import zmq

from .BoundingBox import BoundingBox
from .Cluster import Cluster
from .ConfigurationService import ConfigurationService
from .CCDCaptureModel import CCDCaptureModel
from .EPSDataClasses import (
    ClassificationUpdateRequest,
    ClusterQueryFilter,
    ClusterStoreRequest,
    EPSClusterRecord,
    EPSFitsRecord,
    FitsQueryFilter,
    FitsClusterQueryFilter,
)
from .EventRepository import EventRepository

logger = logging.getLogger(__name__)

_DEFAULT_CLUSTER_IPC = "ipc:///tmp/EPCCluster.ipc"
_DEFAULT_FITS_IPC = "ipc:///tmp/EPCFits.ipc"
_DEFAULT_TIMEOUT_MS = 5000

class ZMQBasedEventRepository(EventRepository):
    """Concrete ``EventRepository`` backed by the EPS ZMQ protocol.

    Constructor accepts an optional ``zmq.Context`` for testability
    (inject a mock context in unit tests).
    """

    def __init__(
        self,
        config: ConfigurationService,
        context: Optional[zmq.Context] = None,
    ):
        self._config = config
        self._ctx = context or zmq.Context.instance()

    def _run_async(self,
                   function: Callable,
                   callback: Callable,
                   on_error: Callable
                   ) -> None:
        """Helper method to run Event Repository retrieval functions asynchronously."""
        def async_wrapper():
            try:
                result = function()
                callback(result)
            except Exception as exc:
                logger.warning("Error in async operation: %s", exc, exc_info=True)
                on_error(str(exc))
        thread = threading.Thread(target=async_wrapper, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Async Wrappers for Public API
    # ------------------------------------------------------------------

    def fetch_events(
            self,
            callback: Callable,
            on_error: Callable
    ) -> None:
        """Returns all cluster events from the EPS asynchronously."""
        self._run_async(
            function=lambda: self.query_clusters_sync(query_filter=None),
            callback=callback,
            on_error=on_error
        )

    def query_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        callback: Callable,
        on_error: Callable
    ) -> None:
        """Initiates a query_cluster function asnychronously with the _run_async function."""
        self._run_async(
            function=lambda: self.query_clusters_sync(query_filter=query_filter),
            callback=callback,
            on_error=on_error
        )

    def query_fits(
        self,
        query_filter: Optional[FitsQueryFilter],
        callback: Callable,
        on_error: Callable
    ) -> None:
        """Initiates a query_fits function asnychronously with the _run_async function."""
        self._run_async(
            function=lambda: self.query_fits_sync(query_filter=query_filter),
            callback=callback,
            on_error=on_error
        )

    def query_fits_clusters(
        self,
        query_filter: Optional[FitsClusterQueryFilter],
        callback: Callable,
        on_error: Callable
    ) -> None:
        """Initiates a query_fits_clusters function asnychronously with the _run_async function."""
        self._run_async(
            function=lambda: self.query_fits_clusters_sync(query_filter=query_filter),
            callback=callback,
            on_error=on_error
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query_clusters_sync(
        self,
        query_filter: Optional[ClusterQueryFilter] = None
    ) -> List[Cluster]:
        """Sends a filtered retrieval request to the EPS Cluster socket."""
        if query_filter is not None:
            request = query_filter.to_eps_dict()
        else:
            request = {"Action": "Retrieval"}

        response = self._send_cluster(request)
        if response is None:
            return []

        if response.get("result") != "success":
            logger.warning(
                "EPS cluster query returned failure: %s",
                response.get("result"),
            )
            raise Exception(f"EPS cluster query failed: {response.get('result')}")

        raw_clusters = response.get("clusters", [])
        clusters: List[Cluster] = []
        for raw in raw_clusters:
            record = EPSClusterRecord.from_eps_dict(raw)
            fitsFilename = record.filename
            fits_date = record.date
            cluster = self._map_to_cluster(record, fitsFilename, fits_date)
            if cluster is not None:
                clusters.append(cluster)
        return clusters

    def store_cluster(self, request: ClusterStoreRequest) -> Optional[int]:
        """Sends a storage request to the EPS Cluster socket."""
        response = self._send_cluster(request.to_eps_dict())
        if response is None:
            return None
        if response.get("result") != "success":
            logger.warning(
                "EPS store_cluster returned failure: %s",
                response.get("result"),
            )
            return None
        return response.get("cluster_id")

    def update_classification(self, request: ClassificationUpdateRequest) -> bool:
        """Sends a classification update to the EPS Cluster socket."""
        response = self._send_cluster(request.to_eps_dict())
        if response is None:
            return False
        if response.get("result") != "success":
            logger.warning(
                "EPS update_classification returned failure: %s",
                response.get("result"),
            )
            return False
        return True

    def query_fits_sync(
        self, query_filter: Optional[FitsQueryFilter] = None
    ) -> List[EPSFitsRecord]:
        """Sends a retrieval request to the EPS FITS socket."""
        if query_filter is not None:
            request = query_filter.to_eps_dict()
        else:
            request = {"Action": "Retrieval"}
        response = self._send_fits(request)
        if response is None:
            return []
        if response.get("result") != "success":
            logger.warning(
                "EPS fits query returned failure: %s",
                response.get("result"),
            )
            raise Exception(f"EPS fits query failed: {response.get('result')}")
        raw_files = response.get("fits", [])
        return [EPSFitsRecord.from_eps_dict(f) for f in raw_files]

    def query_fits_clusters_sync(
        self, query_filter: Optional[FitsClusterQueryFilter] = None
    ) -> List[EPSFitsRecord]:
        """Sends a retrieval request to the EPS FITS socket."""
        if query_filter is not None:
            request = query_filter.to_eps_dict()
        else:
            request = {"Action": "Clusters"}
        response = self._send_fits(request)
        if response is None:
            return []
        if response.get("result") != "success":
            logger.warning(
                "EPS fits query returned failure: %s",
                response.get("result"),
            )
            raise Exception(f"EPS fits query failed: {response.get('result')}")
        raw_clusters = response.get("clusters", [])
        clusters: List[Cluster] = []
        for raw in raw_clusters:
            record = EPSClusterRecord.from_eps_dict(raw)
            fitsFilename = record.filename
            fits_date = record.date
            cluster = self._map_to_cluster(record, fitsFilename, fits_date)
            if cluster is not None:
                clusters.append(cluster)
        return clusters

    # ------------------------------------------------------------------
    # Socket helpers
    # ------------------------------------------------------------------

    def _get_timeout(self) -> int:
        return int(self._config.get("eps:timeout_ms", _DEFAULT_TIMEOUT_MS))

    def _send_cluster(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        addr = str(self._config.get("eps:cluster_ipc", _DEFAULT_CLUSTER_IPC))
        return self._send(addr, request)

    def _send_fits(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        addr = str(self._config.get("eps:fits_ipc", _DEFAULT_FITS_IPC))
        return self._send(addr, request)

    def _send(self, address: str, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Opens a fresh REQ socket, sends *request*, and returns the reply.

        Returns ``None`` on ZMQ errors or timeouts.
        """
        socket: Optional[zmq.Socket] = None
        try:
            socket = self._ctx.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 0)
            socket.setsockopt(zmq.RCVTIMEO, self._get_timeout())
            socket.setsockopt(zmq.SNDTIMEO, self._get_timeout())
            socket.connect(address)
            socket.send_json(request)
            response = socket.recv_json()
            return response
        except zmq.ZMQError as exc:
            logger.warning(
                "ZMQ error communicating with EPS at %s: %s",
                address,
                exc,
            )
            return None
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Invalid JSON response from EPS at %s: %s",
                address,
                exc,
            )
            return None
        finally:
            if socket is not None:
                socket.close()

    # ------------------------------------------------------------------
    # Domain mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_to_cluster(
        record: EPSClusterRecord, fitsFilename: str, date: str
    ) -> Optional[Cluster]:
        """Converts an ``EPSClusterRecord`` to a domain ``Cluster``.

        Handles the gaps between the EPS response and the frontend
        model:

        - **bounding box**: synthesised from data shape (EPS does not
          include it in the response).
        - **classification scores**: defaulted to 0.0 (EPS stores a
          single string, not per-model floats).
        """
        try:
            bbox = BoundingBox(
                top=record.bounding_box["top"],
                left=record.bounding_box["left"],
                bottom=record.bounding_box["bottom"],
                right=record.bounding_box["right"],
            )

            return Cluster(
                boundingBox=bbox,
                data=None,
                centerX=None,
                centerY=None,
                sigmaX=record.sigma_x,
                sigmaY=record.sigma_y,
                energy=record.total_energy,
                pixelCount=record.total_pixels,
                fitsFilename=fitsFilename,
                date=date,
                fitsId=record.fits_id,
                clusterId=record.cluster_id,
                classification=record.classification,
                cnnClassification=0.0,
                nrgClassification=0.0,
                bdtClassification=0.0,
                hdu_id=record.hdu_id,
            )
        except Exception:
            logger.warning(
                "Failed to map EPS cluster %d to domain model",
                record.cluster_id,
                exc_info=True,
            )
            return None
