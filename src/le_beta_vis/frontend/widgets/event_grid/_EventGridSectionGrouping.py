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


def merge_or_append_sections(
    existing: Sequence[SectionInfo],
    new_clusters: Sequence[Cluster],
    new_chunk_offset: int,
) -> List[SectionInfo]:
    """Appends a newly-fetched chunk's sections onto *existing*.

    If the first section of *new_clusters* shares ``(date_part,
    file_part)`` with *existing*'s last section, that last section's
    count is extended in place rather than duplicated.

    Args:
        existing: Current section list (global ``start_index`` values).
        new_clusters: The newly-fetched chunk only (not the full list).
        new_chunk_offset: Global index where *new_clusters* begins.

    Returns:
        A new list of :class:`SectionInfo` (*existing* is not
        mutated), with global ``start_index`` values throughout.
    """
    chunk_sections = group_clusters(new_clusters)
    for section in chunk_sections:
        section.start_index += new_chunk_offset
    if not chunk_sections:
        return list(existing)
    if not existing:
        return chunk_sections

    result = list(existing)
    last = result[-1]
    first_new = chunk_sections[0]
    if (last.date_part, last.file_part) == (first_new.date_part, first_new.file_part):
        result[-1] = SectionInfo(
            date_part=last.date_part,
            file_part=last.file_part,
            start_index=last.start_index,
            count=last.count + first_new.count,
        )
        result.extend(chunk_sections[1:])
    else:
        result.extend(chunk_sections)
    return result


def merge_or_prepend_sections(
    existing: Sequence[SectionInfo],
    new_clusters: Sequence[Cluster],
    new_chunk_offset: int,
) -> List[SectionInfo]:
    """Prepends a newly-fetched chunk's sections onto *existing*.

    Mirror image of :func:`merge_or_append_sections`: merges the new
    chunk's last section into *existing*'s first section if they
    share a key, otherwise inserts the new sections at the front.

    Args:
        existing: Current section list (global ``start_index`` values).
        new_clusters: The newly-fetched chunk only (not the full list).
        new_chunk_offset: Global index where *new_clusters* begins
            (the new, smaller window start).

    Returns:
        A new list of :class:`SectionInfo`, global ``start_index``
        values throughout.
    """
    chunk_sections = group_clusters(new_clusters)
    for section in chunk_sections:
        section.start_index += new_chunk_offset
    if not chunk_sections:
        return list(existing)
    if not existing:
        return chunk_sections

    result = list(existing)
    first_existing = result[0]
    last_new = chunk_sections[-1]
    if (first_existing.date_part, first_existing.file_part) == (
        last_new.date_part, last_new.file_part,
    ):
        result[0] = SectionInfo(
            date_part=first_existing.date_part,
            file_part=first_existing.file_part,
            start_index=last_new.start_index,
            count=last_new.count + first_existing.count,
        )
        result[0:0] = chunk_sections[:-1]
    else:
        result[0:0] = chunk_sections
    return result


@dataclass
class EvictionResult:
    """Outcome of trimming sections at one edge of the loaded window.

    Attributes:
        sections: Updated section list after trimming (a new list;
            the input is not mutated).
        removed_section_count: Number of whole sections removed
            (excludes a partially-trimmed boundary section, which
            survives with a reduced count).
        removed_row_count: Total cluster rows removed across all
            affected sections (whole + partial).
        boundary_partially_trimmed: True if one surviving section had
            its ``start_index``/``count`` adjusted rather than being
            deleted outright (a section straddling the evicted page's
            boundary).
    """

    sections: List[SectionInfo]
    removed_section_count: int
    removed_row_count: int
    boundary_partially_trimmed: bool


def evict_front_sections(
    sections: Sequence[SectionInfo],
    global_count: int,
) -> EvictionResult:
    """Removes the first *global_count* rows' worth of sections.

    A section whose range straddles the evicted boundary (starts
    before the cut, ends after it) is partially trimmed — its
    ``start_index`` advances and ``count`` shrinks by however many of
    its rows fall inside the evicted range — rather than deleted.
    Every other surviving section's ``start_index`` is left untouched,
    since all values are already global.

    Args:
        sections: Current section list, global ``start_index`` values.
        global_count: Number of leading rows to remove.

    Returns:
        :class:`EvictionResult` describing the trimmed list.
    """
    if not sections or global_count <= 0:
        return EvictionResult(list(sections), 0, 0, False)

    cut = sections[0].start_index + global_count
    result: List[SectionInfo] = []
    removed_sections = 0
    removed_rows = 0
    partial = False
    for section in sections:
        sec_end = section.start_index + section.count
        if sec_end <= cut:
            removed_sections += 1
            removed_rows += section.count
            continue
        if section.start_index < cut < sec_end:
            trimmed = cut - section.start_index
            removed_rows += trimmed
            partial = True
            result.append(SectionInfo(
                date_part=section.date_part,
                file_part=section.file_part,
                start_index=cut,
                count=section.count - trimmed,
            ))
        else:
            result.append(section)
    return EvictionResult(result, removed_sections, removed_rows, partial)


def evict_back_sections(
    sections: Sequence[SectionInfo],
    global_count: int,
) -> EvictionResult:
    """Removes the last *global_count* rows' worth of sections.

    Mirror of :func:`evict_front_sections`: a section straddling the
    evicted boundary keeps its ``start_index`` unchanged and only its
    ``count`` shrinks (rows removed from its tail).

    Args:
        sections: Current section list, global ``start_index`` values.
        global_count: Number of trailing rows to remove.

    Returns:
        :class:`EvictionResult` describing the trimmed list.
    """
    if not sections or global_count <= 0:
        return EvictionResult(list(sections), 0, 0, False)

    total_end = sections[-1].start_index + sections[-1].count
    cut = total_end - global_count
    result: List[SectionInfo] = []
    removed_sections = 0
    removed_rows = 0
    partial = False
    for section in sections:
        sec_start = section.start_index
        sec_end = section.start_index + section.count
        if sec_start >= cut:
            removed_sections += 1
            removed_rows += section.count
            continue
        if sec_start < cut < sec_end:
            trimmed = sec_end - cut
            removed_rows += trimmed
            partial = True
            result.append(SectionInfo(
                date_part=section.date_part,
                file_part=section.file_part,
                start_index=sec_start,
                count=section.count - trimmed,
            ))
        else:
            result.append(section)
    return EvictionResult(result, removed_sections, removed_rows, partial)
