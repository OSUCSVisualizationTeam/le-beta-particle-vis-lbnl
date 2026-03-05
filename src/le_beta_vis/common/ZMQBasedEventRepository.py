"""ZMQ-backed EventRepository that talks to Troy's EPS over IPC sockets.

Uses a fresh ``zmq.REQ`` socket per request to avoid REQ/REP state
machine issues on timeout.  All methods are safe to call when the EPS
is down — they return empty/default values and log warnings.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import zmq

from .BoundingBox import BoundingBox
from .Cluster import Cluster
from .ConfigurationService import ConfigurationService
from .CCDCaptureModel import extractClusterFromFile
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_events(self) -> List[Cluster]:
        """Returns all cluster events from the EPS."""
        return self.query_clusters(query_filter=None)

    def query_clusters(
        self, query_filter: Optional[ClusterQueryFilter] = None
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
            return []

        raw_clusters = response.get("clusters", [])
        clusters: List[Cluster] = []
        for raw in raw_clusters:
            record = EPSClusterRecord.from_eps_dict(raw)
            filename = self.query_fits(FitsQueryFilter(fits_id=record.fits_id))[0].filename
            cluster = self._map_to_cluster(record, filename)
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

    def query_fits(self, query_filter: Optional[FitsQueryFilter] = None) -> List[EPSFitsRecord]:
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
            return []
        raw_files = response.get("fits", [])
        return [EPSFitsRecord.from_eps_dict(f) for f in raw_files]
    
    def query_fits_clusters(self, query_filter: Optional[FitsClusterQueryFilter] = None) -> List[EPSFitsRecord]:
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
            return []
        raw_clusters = response.get("clusters", [])
        clusters: List[Cluster] = []
        filename = self.query_fits(FitsQueryFilter)
        for raw in raw_clusters:
            record = EPSClusterRecord.from_eps_dict(raw)
            filename = self.query_fits(FitsQueryFilter(fits_id=record.fits_id))[0].filename
            cluster = self._map_to_cluster(record, filename)
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
    def _map_to_cluster(record: EPSClusterRecord, filename: str) -> Optional[Cluster]:
        """Converts an ``EPSClusterRecord`` to a domain ``Cluster``.

        Handles the gaps between the EPS response and the frontend
        model:

        - **data**: ``np.frombuffer`` if bytes, ``np.array`` if list.
          Attempts square reshape; falls back to 1-row.
        - **bounding box**: synthesised from data shape (EPS does not
          include it in the response).
        - **center**: brightest pixel via ``np.argmax``.
        - **classification scores**: defaulted to 0.0 (EPS stores a
          single string, not per-model floats).
        """
        try:
            bbox = BoundingBox(top=record.bounding_box["top"] , left=record.bounding_box["left"], 
                               bottom=record.bounding_box["bottom"], right=record.bounding_box["right"])
            arr = extractClusterFromFile(fits_filepath=filename, hdu=record.hdu_id, bounding_box=bbox)
            rows, cols = arr.shape
            if arr.size > 0:
                flat_idx = int(np.argmax(arr))
                center_y, center_x = divmod(flat_idx, cols)
            else:
                center_x, center_y = 0, 0
            return Cluster(
                boundingBox=bbox,
                data=arr,
                centerX=center_x,
                centerY=center_y,
                sigmaX=record.sigma_x,
                sigmaY=record.sigma_y,
                energy=record.total_energy,
                pixelCount=record.total_pixels,
                fitsId=record.fits_id,
                clusterId=record.cluster_id,
                classification = record.classification,
                cnnClassification=0.0,
                nrgClassification=0.0,
                bdtClassification=0.0,
            )
        except Exception:
            logger.warning(
                "Failed to map EPS cluster %d to domain model",
                record.cluster_id,
                exc_info=True,
            )
            return None
