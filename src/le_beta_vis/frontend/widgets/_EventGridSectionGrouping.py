"""Pure-Python grouping and index-mapping logic for sectioned event grids.

This module has **no Qt imports** so it can be unit-tested without
a running ``QApplication``.
"""

import bisect
import os
from dataclasses import dataclass
from itertools import groupby
from typing import List, Optional, Sequence, Tuple

from le_beta_vis.common.Cluster import Cluster


@dataclass
class SectionInfo:
    """Describes one contiguous group of clusters in the flat event list.

    Attributes:
        date_part: Day-level date string (``YYYY-MM-DD``) or ``None``.
        file_part: FITS basename (e.g. ``exposure.fits``) or ``None``.
        start_index: Flat index of the first cluster in this section.
        count: Number of clusters in this section.
    """

    date_part: Optional[str]
    file_part: Optional[str]
    start_index: int
    count: int


def _section_key(cluster: Cluster) -> Tuple[Optional[str], Optional[str]]:
    """Extract the ``(date_day, filename_base)`` grouping key."""
    date_part: Optional[str] = None
    if cluster.date is not None:
        try:
            date_part = cluster.date[:10]
        except (TypeError, IndexError):
            date_part = None

    file_part: Optional[str] = None
    if cluster.fitsFilename is not None:
        file_part = os.path.basename(cluster.fitsFilename)

    return (date_part, file_part)


def group_clusters(clusters: Sequence[Cluster]) -> List[SectionInfo]:
    """Group a flat list of clusters into contiguous sections.

    Consecutive clusters sharing the same ``(date[:10], basename(fitsFilename))``
    key are collapsed into a single :class:`SectionInfo`.  Order is preserved;
    non-contiguous duplicates produce separate sections.

    Args:
        clusters: Ordered sequence of clusters from the repository.

    Returns:
        List of section descriptors.  Empty when *clusters* is empty.
    """
    sections: List[SectionInfo] = []
    offset = 0
    for key, group in groupby(clusters, key=_section_key):
        count = sum(1 for _ in group)
        sections.append(SectionInfo(
            date_part=key[0],
            file_part=key[1],
            start_index=offset,
            count=count,
        ))
        offset += count
    return sections


def flat_index_to_section(
    sections: Sequence[SectionInfo],
    flat_index: int,
) -> Tuple[int, int]:
    """Map a flat event index to ``(section_index, local_index)``.

    Uses binary search over :attr:`SectionInfo.start_index` values.

    Args:
        sections: Section list produced by :func:`group_clusters`.
        flat_index: Zero-based index into the original flat cluster list.

    Returns:
        ``(section_index, local_index)`` within that section.

    Raises:
        IndexError: If *flat_index* is out of range.
    """
    if not sections:
        raise IndexError(f"flat_index {flat_index} out of range (no sections)")

    starts = [s.start_index for s in sections]
    sec_idx = bisect.bisect_right(starts, flat_index) - 1

    if sec_idx < 0:
        raise IndexError(f"flat_index {flat_index} out of range")

    section = sections[sec_idx]
    local = flat_index - section.start_index
    if local < 0 or local >= section.count:
        raise IndexError(
            f"flat_index {flat_index} out of range for section {sec_idx}"
        )
    return (sec_idx, local)
