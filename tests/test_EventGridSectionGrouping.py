"""Unit tests for _section_grouping — pure Python, no QApplication needed."""

import numpy as np
import pytest

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.widgets._section_grouping import (
    SectionInfo,
    flat_index_to_section,
    group_clusters,
)


def _make_cluster(
    date: str | None = None,
    fits_filename: str | None = None,
) -> Cluster:
    """Create a minimal Cluster stub for grouping tests."""
    return Cluster(
        boundingBox=BoundingBox(top=0, left=0, bottom=1, right=1),
        data=np.zeros((1, 1), dtype=np.float64),
        centerX=0,
        centerY=0,
        date=date,
        fitsFilename=fits_filename,
    )


# ------------------------------------------------------------------ #
# group_clusters                                                       #
# ------------------------------------------------------------------ #


class TestGroupClusters:
    def test_empty_list_returns_empty(self) -> None:
        assert group_clusters([]) == []

    def test_single_cluster_creates_one_section(self) -> None:
        clusters = [_make_cluster("2026-03-15T12:00:00", "/data/exp.fits")]
        sections = group_clusters(clusters)
        assert len(sections) == 1
        assert sections[0].date_part == "2026-03-15"
        assert sections[0].file_part == "exp.fits"
        assert sections[0].start_index == 0
        assert sections[0].count == 1

    def test_same_key_collapses_into_one_section(self) -> None:
        clusters = [
            _make_cluster("2026-03-15T10:00:00", "/data/exp.fits"),
            _make_cluster("2026-03-15T11:00:00", "/data/exp.fits"),
            _make_cluster("2026-03-15T12:00:00", "/data/exp.fits"),
        ]
        sections = group_clusters(clusters)
        assert len(sections) == 1
        assert sections[0].count == 3

    def test_different_dates_create_separate_sections(self) -> None:
        clusters = [
            _make_cluster("2026-03-15T10:00:00", "/data/exp.fits"),
            _make_cluster("2026-03-16T10:00:00", "/data/exp.fits"),
        ]
        sections = group_clusters(clusters)
        assert len(sections) == 2
        assert sections[0].date_part == "2026-03-15"
        assert sections[1].date_part == "2026-03-16"

    def test_different_filenames_create_separate_sections(self) -> None:
        clusters = [
            _make_cluster("2026-03-15T10:00:00", "/data/a.fits"),
            _make_cluster("2026-03-15T10:00:00", "/data/b.fits"),
        ]
        sections = group_clusters(clusters)
        assert len(sections) == 2
        assert sections[0].file_part == "a.fits"
        assert sections[1].file_part == "b.fits"

    def test_start_indices_are_correct(self) -> None:
        clusters = [
            _make_cluster("2026-03-15T10:00:00", "a.fits"),
            _make_cluster("2026-03-15T10:00:00", "a.fits"),
            _make_cluster("2026-03-16T10:00:00", "b.fits"),
            _make_cluster("2026-03-17T10:00:00", "c.fits"),
            _make_cluster("2026-03-17T10:00:00", "c.fits"),
            _make_cluster("2026-03-17T10:00:00", "c.fits"),
        ]
        sections = group_clusters(clusters)
        assert len(sections) == 3
        assert sections[0].start_index == 0
        assert sections[0].count == 2
        assert sections[1].start_index == 2
        assert sections[1].count == 1
        assert sections[2].start_index == 3
        assert sections[2].count == 3

    def test_none_date_and_filename(self) -> None:
        clusters = [_make_cluster(None, None)]
        sections = group_clusters(clusters)
        assert len(sections) == 1
        assert sections[0].date_part is None
        assert sections[0].file_part is None

    def test_non_contiguous_same_key_creates_separate_sections(self) -> None:
        clusters = [
            _make_cluster("2026-03-15T10:00:00", "a.fits"),
            _make_cluster("2026-03-16T10:00:00", "b.fits"),
            _make_cluster("2026-03-15T10:00:00", "a.fits"),
        ]
        sections = group_clusters(clusters)
        assert len(sections) == 3
        assert sections[0].date_part == "2026-03-15"
        assert sections[2].date_part == "2026-03-15"

    def test_basename_strips_directory(self) -> None:
        clusters = [_make_cluster("2026-01-01", "/long/path/to/file.fits")]
        sections = group_clusters(clusters)
        assert sections[0].file_part == "file.fits"

    def test_date_truncated_to_day(self) -> None:
        clusters = [
            _make_cluster("2026-03-15T10:00:00", "a.fits"),
            _make_cluster("2026-03-15T23:59:59", "a.fits"),
        ]
        sections = group_clusters(clusters)
        assert len(sections) == 1
        assert sections[0].date_part == "2026-03-15"


# ------------------------------------------------------------------ #
# flat_index_to_section                                                #
# ------------------------------------------------------------------ #


class TestFlatIndexToSection:
    @pytest.fixture()
    def three_sections(self) -> list[SectionInfo]:
        return [
            SectionInfo("2026-03-15", "a.fits", start_index=0, count=2),
            SectionInfo("2026-03-16", "b.fits", start_index=2, count=1),
            SectionInfo("2026-03-17", "c.fits", start_index=3, count=3),
        ]

    def test_first_section_first_item(self, three_sections) -> None:
        assert flat_index_to_section(three_sections, 0) == (0, 0)

    def test_first_section_last_item(self, three_sections) -> None:
        assert flat_index_to_section(three_sections, 1) == (0, 1)

    def test_second_section(self, three_sections) -> None:
        assert flat_index_to_section(three_sections, 2) == (1, 0)

    def test_third_section_first(self, three_sections) -> None:
        assert flat_index_to_section(three_sections, 3) == (2, 0)

    def test_third_section_last(self, three_sections) -> None:
        assert flat_index_to_section(three_sections, 5) == (2, 2)

    def test_out_of_range_raises(self, three_sections) -> None:
        with pytest.raises(IndexError):
            flat_index_to_section(three_sections, 6)

    def test_negative_raises(self, three_sections) -> None:
        with pytest.raises(IndexError):
            flat_index_to_section(three_sections, -1)

    def test_empty_sections_raises(self) -> None:
        with pytest.raises(IndexError):
            flat_index_to_section([], 0)
