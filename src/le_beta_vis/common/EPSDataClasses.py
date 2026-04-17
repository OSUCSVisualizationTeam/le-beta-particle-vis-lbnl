"""Request/response DTOs for the Event Persistence Service (EPS) ZMQ protocol.

Each class maps to a specific JSON message exchanged over the EPS IPC
sockets.  All classes are frozen dataclasses with conversion helpers
(``to_eps_dict`` for requests, ``from_eps_dict`` for responses).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

_DATE_FILTER_FORMAT = "%Y-%m-%d %H:%M:%S"


def _validate_date_range(
    date_start: Optional[datetime],
    date_end: Optional[datetime],
) -> None:
    """Shared validator for date_start/date_end pairs on EPS query DTOs.

    Raises ``TypeError`` if either field is set but not a ``datetime``,
    and ``ValueError`` if both are set and ``date_start > date_end``.
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

    Any field left as ``None`` is omitted from the request, meaning
    the EPS will not filter on that criterion.
    """

    cluster_id: Optional[int] = None
    fits_id: Optional[int] = None
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


@dataclass(frozen=True)
class ClusterRecentQueryFilter:
    """Request for the EPS RecentRetrieval action.

    Returns clusters ordered by FITS date descending, paginated via
    ``limit`` and ``offset``. Intended for the Live Mode fallback
    provider and other newest-first consumers.
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
        }


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


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EPSClusterRecord:
    """A single cluster record from an EPS Cluster Retrieval response."""

    fits_id: int
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

        The EPS returns ``"min"`` and ``"max"`` keys (not
        ``"minimum"``/``"maximum"``).
        """
        return EPSFitsRecord(
            fits_id=int(d.get("fits_id", 0)),
            filename=str(d.get("filename", "")),
            date=str(d.get("date", "")),
            min_val=float(d.get("min", 0.0)),
            max_val=float(d.get("max", 0.0)),
            exposure_time=float(d.get("exposure_time", 0.0)),
        )
