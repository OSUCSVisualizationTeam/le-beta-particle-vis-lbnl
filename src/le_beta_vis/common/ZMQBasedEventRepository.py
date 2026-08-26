"""ZMQ-backed EventRepository that talks to Troy's EPS over IPC sockets.

Uses a fresh ``zmq.REQ`` socket per request to avoid REQ/REP state
machine issues on timeout.  All methods are safe to call when the EPS
is down — they return empty/default values and log warnings.
"""

import json
import logging
import math
import warnings
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
    ClusterPagedQueryFilter,
    ClusterQueryFilter,
    ClusterRecentQueryFilter,
    ClusterStoreRequest,
    EPSClusterRecord,
    EPSFitsRecord,
    FitsClusterQueryFilter,
    FitsQueryFilter,
    FitsStoreRequest,
    PagedRetrieveClustersResponse,
)
from .EventRepository import (
    Dispatcher,
    EventRepository,
    onCluster,
    onError,
    onFits,
    onUpdate,
)

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
        dispatcher: Optional[Dispatcher] = None,
    ):
        self._config = config
        self._ctx = context or zmq.Context.instance()
        self._dispatch: Dispatcher = dispatcher or (lambda fn: fn())

    def _run_async(self,
                   function: Callable,
                   callback: Callable,
                   on_error: Callable
                   ) -> None:
        """Helper method to run Event Repository retrieval functions asynchronously."""
        def async_wrapper():
            try:
                result = function()
                self._dispatch(lambda: callback(result))
            except Exception as exc:
                logger.warning("Error in async operation: %s", exc, exc_info=True)
                message = str(exc)
                self._dispatch(lambda: on_error(message))
        thread = threading.Thread(target=async_wrapper, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Async Wrappers for Public API
    # ------------------------------------------------------------------

    def fetch_events(
            self,
            callback: onCluster,
            on_error: onError
    ) -> None:
        """Returns all cluster events from the EPS asynchronously.

        .. deprecated::
            Sends an unbounded ``{"Action": "Retrieval"}`` request — the
            EPS may return its entire `clusters` table in one reply. Use
            :meth:`fetch_clusters` instead, which sends a bounded
            ``PagedRetrieval`` request.
        """
        warnings.warn(
            "fetch_events sends an unbounded request; use fetch_clusters instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._run_async(
            function=lambda: self.query_clusters_sync(query_filter=None),
            callback=callback,
            on_error=on_error
        )

    def fetch_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        limit: Optional[int],
        offset: int,
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Initiates a bounded PagedRetrieval request asynchronously."""
        self._run_async(
            function=lambda: self.fetch_clusters_sync(query_filter, limit, offset),
            callback=callback,
            on_error=on_error,
        )

    def fetch_clusters_sync(
        self,
        query_filter: Optional[ClusterQueryFilter] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Cluster]:
        """Sends a bounded PagedRetrieval request to the EPS Cluster socket.

        ``limit`` defaults to ``eps:retrieval_limit_default`` when not
        supplied. Callers may override it (e.g. for a smaller page size),
        but the EPS enforces ``eps:retrieval_limit_max`` regardless.
        """
        if limit is None:
            limit = int(self._config.get("eps:retrieval_limit_default", 500))

        paged_filter = ClusterPagedQueryFilter(
            filters=query_filter or ClusterQueryFilter(),
            limit=limit,
            offset=offset,
        )

        response = self._send_cluster(paged_filter.to_eps_dict())
        if response is None:
            return []

        paged = PagedRetrieveClustersResponse(
            result=response.get("result", "failure"),
            clusters=response.get("clusters"),
            limit=response.get("limit", 0),
            offset=response.get("offset", 0),
            error=response.get("error"),
        )
        if not paged.is_success:
            logger.warning(
                "EPS paged cluster query returned failure: %s", paged.error
            )
            raise Exception(f"EPS paged cluster query failed: {paged.error}")

        clusters: List[Cluster] = []
        for raw in (paged.clusters or []):
            record = EPSClusterRecord.from_eps_dict(raw)
            cluster = self._map_to_cluster(record, record.filename, record.date)
            if cluster is not None:
                clusters.append(cluster)
        return clusters

    def query_clusters(
        self,
        query_filter: Optional[ClusterQueryFilter],
        callback: onCluster,
        on_error: onError
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
        callback: onFits,
        on_error: onError
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

    def query_recent_clusters(
        self,
        limit: int,
        offset: int,
        callback: onCluster,
        on_error: onError,
    ) -> None:
        """Initiates a RecentRetrieval request asynchronously."""
        self._run_async(
            function=lambda: self.query_recent_clusters_sync(
                limit=limit, offset=offset
            ),
            callback=callback,
            on_error=on_error,
        )

    def query_recent_clusters_sync(
        self, limit: int, offset: int = 0
    ) -> List[Cluster]:
        """Sends a RecentRetrieval request to the EPS Cluster socket."""
        request = ClusterRecentQueryFilter(
            limit=limit, offset=offset
        ).to_eps_dict()

        response = self._send_cluster(request)
        if response is None:
            return []

        if response.get("result") != "success":
            logger.warning(
                "EPS recent cluster query returned failure: %s",
                response.get("result"),
            )
            return []

        raw_clusters = response.get("clusters", [])
        clusters: List[Cluster] = []
        for raw in raw_clusters:
            record = EPSClusterRecord.from_eps_dict(raw)
            cluster = self._map_to_cluster(
                record, record.filename, record.date
            )
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

    def store_fits_sync(self, request: FitsStoreRequest) -> Optional[int]:
        """Registers a FITS file in EPS; returns its database ID or None on failure."""
        response = self._send_fits(request.to_eps_dict())
        if response is None:
            return None
        if response.get("result") != "success":
            logger.warning(
                "EPS store_fits returned failure: %s",
                response.get("result"),
            )
            return None
        return response.get("fits_id")

    def update_classification(
            self,
            request: ClassificationUpdateRequest,
            callback: onUpdate,
            on_error: onError
    ) -> None:
        """Sends a classification update to the EPS Cluster socket asynchronously."""
        self._run_async(
            function=lambda: self.update_classification_sync(request),
            callback=callback,
            on_error=on_error,
        )

    def update_classification_sync(
            self,
            request: ClassificationUpdateRequest,
    ) -> bool:
        """Sends a classification update to the EPS Cluster socket."""
        response = self._send_cluster(request.to_eps_dict())
        if response is None:
            raise Exception("Failed to update classification")
        if response.get("result") != "success":
            logger.warning(
                "EPS update_classification returned failure: %s",
                response.get("result"),
            )
            raise Exception(f"EPS update_classification failed: {response.get('result')}")
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
    ) -> List[Cluster]:
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
        - **classification scores**: per-model cnn/nrg/bdt floats round-trip
          from the DB via ``record``; ``None`` (nullable columns, e.g. rows
          classified before this feature existed) is coerced to 0.0.
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
                cnnClassification=record.cnn_classification or 0.0,
                nrgClassification=record.nrg_classification or 0.0,
                bdtClassification=record.bdt_classification or 0.0,
                hdu_id=record.hdu_id,
            )
        except Exception:
            logger.warning(
                "Failed to map EPS cluster %d to domain model",
                record.cluster_id,
                exc_info=True,
            )
            return None
