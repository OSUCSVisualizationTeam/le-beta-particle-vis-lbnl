"""Request/response DTOs for the Event Persistence Service (EPS) ZMQ protocol.

Each class maps to a specific JSON message exchanged over the EPS IPC sockets.  All classes are
frozen dataclasses with conversion helpers (``to_eps_dict`` for requests, ``from_eps_dict`` for
responses).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

_DATE_FILTER_FORMAT = "%Y-%m-%d %H:%M:%S"


def _validate_date_range(
    date_start: Optional[datetime],
    date_end: Optional[datetime],
) -> None:
    """Shared validator for date_start/date_end pairs on EPS query DTOs.

    Raises ``TypeError`` if either field is set but not a ``datetime``, and ``ValueError`` if both
    are set and ``date_start > date_end``.
    """
    if date_start is not None and not isinstance(date_start, datetime):
        raise TypeError(
            f"date_start must be datetime or None, "
            f"got {type(date_start).__name__}"
        )
    if date_end is not None and not isinstance(date_end, datetime):
        raise TypeError(
            f"date_end must be datetime or None, "
            f"got {type(date_end).__name__}"
        )
    if (
        date_start is not None
        and date_end is not None
        and date_start > date_end
    ):
        raise ValueError("date_start must be <= date_end")


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClusterQueryFilter:
    """Filter criteria for an EPS Cluster Retrieval request.

    Any field left as ``None`` is omitted from the request, meaning the EPS will not filter on that
    criterion.
    """

    cluster_id: Optional[int] = None
    fits_id: Optional[int] = None
    fits_list: Optional[List] = None
    hdu_id: Optional[int] = None
    bounding_box: Optional[dict] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    min_sigma_x: Optional[float] = None
    min_sigma_y: Optional[float] = None
    min_total_energy: Optional[float] = None
    min_total_pixels: Optional[int] = None
    classification: Optional[str] = None

    def __post_init__(self) -> None:
        _validate_date_range(self.date_start, self.date_end)

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the EPS Cluster socket."""
        d: Dict[str, Any] = {"Action": "Retrieval"}
        if self.cluster_id is not None:
            d["cluster_id"] = self.cluster_id
        if self.fits_id is not None:
            d["fits_id"] = self.fits_id
        if self.fits_list is not None:
            d["fits_list"] = self.fits_list
        if self.hdu_id is not None:
            d["hdu_id"] = self.hdu_id
        if self.date_start is not None and self.date_end is not None:
            d["date"] = {
                "start": self.date_start.strftime(_DATE_FILTER_FORMAT),
                "end": self.date_end.strftime(_DATE_FILTER_FORMAT),
            }
        if self.bounding_box is not None:
            d["bounding_box"] = self.bounding_box
        if self.min_sigma_x is not None:
            d["sigmaX"] = self.min_sigma_x
        if self.min_sigma_y is not None:
            d["sigmaY"] = self.min_sigma_y
        if self.min_total_energy is not None:
            d["total_energy"] = self.min_total_energy
        if self.min_total_pixels is not None:
            d["total_pixels"] = self.min_total_pixels
        if self.classification is not None:
            d["classification"] = self.classification
        return d

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "ClusterQueryFilter":
        """Parses one ClusterQueryFilter request."""
        date = d.get("date", None)
        return ClusterQueryFilter(
            cluster_id=d.get("cluster_id", None),
            fits_id=d.get("fits_id", None),
            fits_list=d.get("fits_list", None),
            hdu_id=d.get("hdu_id", None),
            bounding_box=d.get("bounding_box", None),
            date_start=datetime.strptime(date.get("start", None), _DATE_FILTER_FORMAT) if date else None,
            date_end=datetime.strptime(date.get("end", None), _DATE_FILTER_FORMAT) if date else None,
            min_sigma_x=d.get("sigmaX", None),
            min_sigma_y=d.get("sigmaY", None),
            min_total_energy=d.get("total_energy", None),
            min_total_pixels=d.get("total_pixels", None),
            classification=d.get("classification", None),
        )


@dataclass(frozen=True)
class ClusterPagedQueryFilter:
    """Request for the EPS PagedRetrieval action.

    Wraps a ``ClusterQueryFilter`` for filter criteria and adds ``limit``/``offset`` pagination
    fields. ``limit`` of ``None`` means the EPS should apply its configured server-side default.
    """

    filters: ClusterQueryFilter = field(default_factory=ClusterQueryFilter)
    limit: Optional[int] = None
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit is not None and (
            not isinstance(self.limit, int) or self.limit <= 0
        ):
            raise ValueError("limit must be a positive int or None")
        if not isinstance(self.offset, int) or self.offset < 0:
            raise ValueError("offset must be a non-negative int")

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict for the PagedRetrieval action."""
        d = self.filters.to_eps_dict()
        d["Action"] = "PagedRetrieval"
        if self.limit is not None:
            d["limit"] = self.limit
        d["offset"] = self.offset
        return d

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "ClusterPagedQueryFilter":
        """Parses one ClusterPagedQueryFilter request."""
        return ClusterPagedQueryFilter(
            filters=ClusterQueryFilter.from_eps_dict(d),
            limit=d.get("limit"),
            offset=d.get("offset", 0),
        )


@dataclass(frozen=True)
class ClusterRecentQueryFilter:
    """Request for the EPS RecentRetrieval action.

    Returns clusters ordered by FITS date descending, paginated via ``limit`` and ``offset``.
    Intended for the Live Mode fallback provider and other newest-first consumers.
    """

    limit: int
    offset: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.limit, int) or self.limit <= 0:
            raise ValueError("limit must be a positive int")
        if not isinstance(self.offset, int) or self.offset < 0:
            raise ValueError("offset must be a non-negative int")

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict for the RecentRetrieval action."""
        return {
            "Action": "RecentRetrieval",
            "limit": self.limit,
            "offset": self.offset,
        }

    @staticmethod
    def from_eps_dict(d: dict[str, any]) -> "ClusterRecentQueryFilter":
        """Parses one ClusterRecentQuery request."""
        return ClusterRecentQueryFilter(
            limit=(d.get("limit")),
            offset=(d.get("offset", 0))
        )


@dataclass(frozen=True)
class FitsQueryFilter:
    """Filter criteria for an EPS FITS Retrieval request."""

    fits_id: Optional[int] = None
    filename: Optional[str] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    exposure_time: Optional[float] = None

    def __post_init__(self) -> None:
        _validate_date_range(self.date_start, self.date_end)

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the EPS FITS socket."""
        d: Dict[str, Any] = {"Action": "Retrieval"}
        if self.fits_id is not None:
            d["fits_id"] = self.fits_id
        if self.filename is not None:
            d["filename"] = self.filename
        if self.date_start is not None and self.date_end is not None:
            d["date"] = {
                "start": self.date_start.strftime(_DATE_FILTER_FORMAT),
                "end": self.date_end.strftime(_DATE_FILTER_FORMAT),
            }
        if self.minimum is not None:
            d["minimum"] = self.minimum
        if self.maximum is not None:
            d["maximum"] = self.maximum
        if self.exposure_time is not None:
            d["exposure_time"] = self.exposure_time
        return d

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "FitsQueryFilter":
        """Parses one FitsQueryFilter request."""
        date = d.get("date", None)
        return FitsQueryFilter(
            fits_id=d.get("fits_id", None),
            filename=d.get("filename", None),
            date_start=datetime.strptime(date.get("start", None), _DATE_FILTER_FORMAT) if date else None,
            date_end=datetime.strptime(date.get("end", None), _DATE_FILTER_FORMAT) if date else None,
            minimum=d.get("minimum", None),
            maximum=d.get("maximum", None),
            exposure_time=d.get("exposure_time", None),
        )


@dataclass(frozen=True)
class FitsClusterQueryFilter:
    """Filter criteria for an EPS FITS Clusters Retrieval request."""

    fits_id: Optional[int] = None
    filename: Optional[str] = None
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    exposure_time: Optional[float] = None

    def __post_init__(self) -> None:
        _validate_date_range(self.date_start, self.date_end)

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the EPS FITS socket."""
        d: Dict[str, Any] = {"Action": "Clusters"}
        if self.fits_id is not None:
            d["fits_id"] = self.fits_id
        if self.filename is not None:
            d["filename"] = self.filename
        if self.date_start is not None and self.date_end is not None:
            d["date"] = {
                "start": self.date_start.strftime(_DATE_FILTER_FORMAT),
                "end": self.date_end.strftime(_DATE_FILTER_FORMAT),
            }
        if self.minimum is not None:
            d["minimum"] = self.minimum
        if self.maximum is not None:
            d["maximum"] = self.maximum
        if self.exposure_time is not None:
            d["exposure_time"] = self.exposure_time
        return d


@dataclass(frozen=True)
class FitsStoreRequest:
    """Payload for an EPS Fits Storage request."""

    filename: str
    date: str
    min: float
    max: float
    exposure_time: float

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the EPS Fits socket."""
        return {
            "Action": "Storage",
            "filename": self.filename,
            "date": self.date,
            "min": self.min,
            "max": self.max,
            "exposure_time": self.exposure_time,
        }

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "FitsStoreRequest":
        """Parses one Fits storage request."""
        return FitsStoreRequest(
            filename=d.get("filename", ""),
            date=str(d.get("date", "")),
            min=d.get("min", 0.0),
            max=d.get("max", 0.0),
            exposure_time=d.get("exposure_time", 0.0),
        )


@dataclass(frozen=True)
class ClusterStoreRequest:
    """Payload for an EPS Cluster Storage request."""

    data: List[Any]
    hdu_id: int
    bounding_box: Dict[str, int]
    sigma_x: float
    sigma_y: float
    total_energy: float
    total_pixels: int
    fits_id: int
    classification: str = ""
    cnn_classification: Optional[float] = None
    nrg_classification: Optional[float] = None
    bdt_classification: Optional[float] = None

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the EPS Cluster socket."""
        return {
            "Action": "Storage",
            "data": self.data,
            "hdu_id": self.hdu_id,
            "bounding_box": self.bounding_box,
            "sigmaX": self.sigma_x,
            "sigmaY": self.sigma_y,
            "total_energy": self.total_energy,
            "total_pixels": self.total_pixels,
            "fits_id": self.fits_id,
            "classification": self.classification,
            "cnn_classification": self.cnn_classification,
            "nrg_classification": self.nrg_classification,
            "bdt_classification": self.bdt_classification,
        }

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "ClusterStoreRequest":
        """Parses one ``clusters`` storage request."""
        return ClusterStoreRequest(
            data=d.get("data", []),
            hdu_id=d.get("hdu_id", 0),
            bounding_box=d.get("bounding_box"),
            sigma_x=float(d.get("sigmaX", 0.0)),
            sigma_y=float(d.get("sigmaY", 0.0)),
            total_energy=float(d.get("total_energy", 0.0)),
            total_pixels=int(d.get("total_pixels", 0)),
            fits_id=d.get("fits_id", 0),
            classification=str(d.get("classification", "")),
            cnn_classification=d.get("cnn_classification"),
            nrg_classification=d.get("nrg_classification"),
            bdt_classification=d.get("bdt_classification"),
        )


@dataclass(frozen=True)
class BulkClusterStoreRequest:
    """Payload for an EPS BulkStorage request.

    Wraps the clusters flushed together from a client-side ClusterStorageBuffer so they can be
    persisted in a single transaction instead of one ``Storage`` request per cluster.
    """

    clusters: List[ClusterStoreRequest]

    def __post_init__(self) -> None:
        if not self.clusters:
            raise ValueError("clusters must be non-empty")

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict expected by the EPS Cluster socket."""
        return {
            "Action": "BulkStorage",
            "clusters": [c.to_eps_dict() for c in self.clusters],
        }

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "BulkClusterStoreRequest":
        """Parses one BulkStorage request."""
        return BulkClusterStoreRequest(
            clusters=[
                ClusterStoreRequest.from_eps_dict(c)
                for c in d.get("clusters", [])
            ]
        )


@dataclass(frozen=True)
class ClassificationUpdateRequest:
    """Payload for updating a cluster's classification string."""

    cluster_id: int
    classification: str

    def to_eps_dict(self) -> Dict[str, Any]:
        """Builds the JSON dict for a classification update."""
        return {
            "Action": "UpdateClassification",
            "cluster_id": self.cluster_id,
            "classification": self.classification,
        }

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "ClassificationUpdateRequest":
        """Parses one ClassificationUpdateRequest."""
        return ClassificationUpdateRequest(
            cluster_id=(d.get("cluster_id", 0)),
            classification=(d.get("classification", ""))
        )

# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EPSClusterRecord:
    """A single cluster record from an EPS Cluster Retrieval response."""

    fits_id: int
    fits_list: Optional[List[int]]
    hdu_id: int
    cluster_id: int
    bounding_box: dict
    data: Any
    total_energy: float
    sigma_x: float
    sigma_y: float
    classification: str
    total_pixels: int
    filename: str
    date: str

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "EPSClusterRecord":
        """Parses one element of the ``clusters`` response array."""
        return EPSClusterRecord(
            fits_id=d.get("fits_id", 0),
            fits_list=d.get("fits_list", []),
            hdu_id=d.get("hdu_id", 0),
            cluster_id=d.get("cluster_id", 0),
            bounding_box=d.get("bounding_box"),
            data=d.get("data", []),
            total_energy=float(d.get("total_energy", 0.0)),
            sigma_x=float(d.get("sigmaX", 0.0)),
            sigma_y=float(d.get("sigmaY", 0.0)),
            classification=str(d.get("classification", "")),
            total_pixels=int(d.get("total_pixels", 0)),
            filename=str(d.get("filename", "")),
            date=str(d.get("date", "")),
        )

    @staticmethod
    def from_db_row(row: Dict[str, Any]) -> "EPSClusterRecord":
        """Parses one ``clusters``/``fits_files`` join row from a dictionary cursor.

        Unlike :meth:`from_eps_dict`, the source keys are database column names (``fitsFile``,
        ``clusterID``, ``box_top``, ``totalEnergy``, ``pixelCount``, ...) rather than the EPS wire-
        format keys. Pixel data is never hydrated from the database — ``data`` is always ``None``.
        """
        return EPSClusterRecord(
            fits_id=row["fitsFile"],
            fits_list=None,
            hdu_id=row["hdu_id"],
            cluster_id=row["clusterID"],
            bounding_box={
                "top": row["box_top"],
                "left": row["box_left"],
                "bottom": row["box_bottom"],
                "right": row["box_right"],
            },
            data=None,
            total_energy=row["totalEnergy"],
            sigma_x=row["sigmaX"],
            sigma_y=row["sigmaY"],
            classification=row["classification"],
            total_pixels=row["pixelCount"],
            filename=row["filename"],
            date=str(row["date"]),
        )

    def to_response_dict(self) -> Dict[str, Any]:
        """Builds the EPS wire-format dict for a single cluster response entry."""
        return {
            "fits_id": self.fits_id,
            "cluster_id": self.cluster_id,
            "hdu_id": self.hdu_id,
            "bounding_box": self.bounding_box,
            "data": self.data,
            "total_energy": self.total_energy,
            "sigmaX": self.sigma_x,
            "sigmaY": self.sigma_y,
            "classification": self.classification,
            "total_pixels": self.total_pixels,
            "filename": self.filename,
            "date": self.date,
        }


@dataclass(frozen=True)
class PagedRetrieveClustersResponse:
    """Typed envelope for a PagedRetrieval EPS response.

    ``clusters`` holds the pre-serialized cluster dicts produced by ``_format_cluster_rows`` so that
    ``dataclasses.asdict()`` round-trips to JSON without any custom serialization logic.
    """

    result: str
    clusters: Optional[List[dict]]
    limit: int
    offset: int
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.result == "success"


@dataclass(frozen=True)
class BulkInsertClustersResponse:
    """Typed envelope for a BulkStorage EPS response.

    ``cluster_ids`` stays positionally aligned with the request's
    cluster list: ``"success"`` yields all ints, ``"partial"``/
    ``"failure"`` yield a mix of ints and ``None`` for rows that
    could not be persisted even by the per-row fallback.
    """

    result: str
    cluster_ids: Optional[List[Optional[int]]]
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.result == "success"


@dataclass(frozen=True)
class EPSFitsRecord:
    """A single FITS file record from an EPS FITS Retrieval response."""

    fits_id: int
    filename: str
    date: str
    min_val: float
    max_val: float
    exposure_time: float

    @staticmethod
    def from_eps_dict(d: Dict[str, Any]) -> "EPSFitsRecord":
        """Parses one element of the EPS FITS response array.

        The EPS returns ``"min"`` and ``"max"`` keys (not ``"minimum"``/``"maximum"``).
        """
        return EPSFitsRecord(
            fits_id=int(d.get("fits_id", 0)),
            filename=str(d.get("filename", "")),
            date=str(d.get("date", "")),
            min_val=float(d.get("min", 0.0)),
            max_val=float(d.get("max", 0.0)),
            exposure_time=float(d.get("exposure_time", 0.0)),
        )
