"""Unit tests for IncomingDataQueue — the unified bounded queue
for the Live Mode cluster display pipeline.
"""

import threading

import pytest
import numpy as np

from le_beta_vis.common.BoundingBox import BoundingBox
from le_beta_vis.common.Cluster import Cluster
from le_beta_vis.frontend.livemode.IncomingDataQueue import IncomingDataQueue


def _make_cluster(label: int = 0) -> Cluster:
    """Creates a minimal Cluster for queue testing."""
    return Cluster(
        boundingBox=BoundingBox(top=0, left=0, bottom=4, right=4),
        data=np.zeros((4, 4), dtype=np.float32),
        centerX=2,
        centerY=2,
        energy=float(label),
        clusterId=label,
    )


# --- Initial state ---


class TestInitialState:
    def test_all_slots_none(self):
        q = IncomingDataQueue(5)
        assert q.snapshot() == [None] * 5

    def test_capacity(self):
        q = IncomingDataQueue(10)
        assert q.capacity == 10

    def test_pointer_zero(self):
        q = IncomingDataQueue(5)
        assert q.pointer == 0

    def test_fresh_count_zero(self):
        q = IncomingDataQueue(5)
        assert q.fresh_count == 0

    def test_not_full(self):
        q = IncomingDataQueue(5)
        assert not q.is_full

    def test_slots_needed_equals_capacity(self):
        q = IncomingDataQueue(5)
        assert q.slots_needed() == 5

    def test_minimum_capacity(self):
        q = IncomingDataQueue(0)
        assert q.capacity == 1


# --- dequeue_front ---


class TestDequeueFront:
    def test_empty_returns_none(self):
        q = IncomingDataQueue(3)
        assert q.dequeue_front() is None

    def test_returns_first_slot(self):
        q = IncomingDataQueue(3)
        c = _make_cluster(1)
        q.append_fallback([c])
        assert q.dequeue_front() is c

    def test_shifts_left(self):
        q = IncomingDataQueue(4)
        clusters = [_make_cluster(i) for i in range(4)]
        q.append_fallback(clusters)
        q.dequeue_front()
        snap = q.snapshot()
        assert snap[0] is clusters[1]
        assert snap[1] is clusters[2]
        assert snap[2] is clusters[3]
        assert snap[3] is None

    def test_decrements_pointer(self):
        q = IncomingDataQueue(5)
        q.insert_fresh([_make_cluster(1), _make_cluster(2)])
        assert q.pointer == 2
        q.dequeue_front()
        assert q.pointer == 1

    def test_pointer_stays_zero_when_no_fresh(self):
        q = IncomingDataQueue(3)
        q.append_fallback([_make_cluster(1)])
        q.dequeue_front()
        assert q.pointer == 0


# --- insert_fresh ---


class TestInsertFresh:
    def test_inserts_at_pointer(self):
        q = IncomingDataQueue(5)
        c = _make_cluster(1)
        q.insert_fresh([c])
        assert q.snapshot()[0] is c

    def test_advances_pointer(self):
        q = IncomingDataQueue(5)
        q.insert_fresh([_make_cluster(1), _make_cluster(2)])
        assert q.pointer == 2

    def test_pushes_fallback_right(self):
        q = IncomingDataQueue(4)
        fb = _make_cluster(99)
        q.append_fallback([fb])
        fresh = _make_cluster(1)
        q.insert_fresh([fresh])
        snap = q.snapshot()
        assert snap[0] is fresh
        assert snap[1] is fb

    def test_truncates_excess_beyond_capacity(self):
        q = IncomingDataQueue(3)
        fallbacks = [_make_cluster(i) for i in range(3)]
        q.append_fallback(fallbacks)
        q.insert_fresh([_make_cluster(10), _make_cluster(11)])
        snap = q.snapshot()
        assert len(snap) == 3
        assert snap[0].clusterId == 10
        assert snap[1].clusterId == 11
        assert snap[2].clusterId == 0

    def test_does_not_exceed_capacity(self):
        q = IncomingDataQueue(3)
        q.insert_fresh([_make_cluster(i) for i in range(10)])
        assert len(q.snapshot()) == 3
        assert q.pointer == 3


# --- append_fallback ---


class TestAppendFallback:
    def test_fills_from_pointer(self):
        q = IncomingDataQueue(5)
        q.insert_fresh([_make_cluster(1)])
        fb = [_make_cluster(10), _make_cluster(11)]
        q.append_fallback(fb)
        snap = q.snapshot()
        assert snap[0].clusterId == 1
        assert snap[1].clusterId == 10
        assert snap[2].clusterId == 11
        assert snap[3] is None
        assert snap[4] is None

    def test_does_not_change_pointer(self):
        q = IncomingDataQueue(5)
        q.insert_fresh([_make_cluster(1)])
        assert q.pointer == 1
        q.append_fallback([_make_cluster(10)])
        assert q.pointer == 1

    def test_skips_non_none_slots(self):
        q = IncomingDataQueue(3)
        q.append_fallback([_make_cluster(1)])
        q.append_fallback([_make_cluster(2)])
        snap = q.snapshot()
        assert snap[0].clusterId == 1
        assert snap[1].clusterId == 2
        assert snap[2] is None

    def test_stops_at_capacity(self):
        q = IncomingDataQueue(3)
        q.append_fallback([_make_cluster(i) for i in range(10)])
        snap = q.snapshot()
        assert all(s is not None for s in snap)
        assert len(snap) == 3


# --- slots_needed ---


class TestSlotsNeeded:
    def test_counts_nones(self):
        q = IncomingDataQueue(5)
        q.append_fallback([_make_cluster(1)])
        assert q.slots_needed() == 4


# --- is_full ---


class TestIsFull:
    def test_full_when_all_occupied(self):
        q = IncomingDataQueue(3)
        q.append_fallback([_make_cluster(i) for i in range(3)])
        assert q.is_full

    def test_not_full_with_nones(self):
        q = IncomingDataQueue(3)
        q.append_fallback([_make_cluster(1)])
        assert not q.is_full


# --- snapshot ---


class TestSnapshot:
    def test_is_independent_copy(self):
        q = IncomingDataQueue(3)
        snap = q.snapshot()
        snap[0] = _make_cluster(99)
        assert q.snapshot()[0] is None


# --- clear ---


class TestClear:
    def test_resets_all(self):
        q = IncomingDataQueue(5)
        q.insert_fresh([_make_cluster(1)])
        q.append_fallback([_make_cluster(2)])
        q.clear()
        assert q.snapshot() == [None] * 5
        assert q.pointer == 0
        assert q.fresh_count == 0


# --- Thread safety ---


class TestThreadSafety:
    def test_concurrent_dequeue_and_append(self):
        """Verifies no crash under concurrent access."""
        q = IncomingDataQueue(100)
        q.append_fallback([_make_cluster(i) for i in range(100)])
        errors = []

        def writer():
            try:
                for i in range(50):
                    q.append_fallback([_make_cluster(1000 + i)])
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    q.dequeue_front()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(5)]
        threads.append(threading.Thread(target=reader))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent access errors: {errors}"
        snap = q.snapshot()
        assert len(snap) == 100
