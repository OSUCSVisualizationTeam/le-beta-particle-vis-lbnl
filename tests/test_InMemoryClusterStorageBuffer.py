"""Tests for InMemoryClusterStorageBuffer / ClusterStorageBuffer."""

import pytest

from le_beta_vis.backend.InMemoryClusterStorageBuffer import InMemoryClusterStorageBuffer


class TestConstruction:

    def test_non_positive_capacity_raises(self):
        with pytest.raises(ValueError):
            InMemoryClusterStorageBuffer(capacity=0, flush_callback=lambda items: items)
        with pytest.raises(ValueError):
            InMemoryClusterStorageBuffer(capacity=-1, flush_callback=lambda items: items)

    def test_capacity_property(self):
        buffer = InMemoryClusterStorageBuffer(capacity=5, flush_callback=lambda items: items)
        assert buffer.capacity == 5


class TestAddAndAutoFlush:

    def test_add_below_capacity_does_not_flush(self):
        calls = []
        buffer = InMemoryClusterStorageBuffer(capacity=3, flush_callback=lambda items: calls.append(items))
        buffer.add(1)
        buffer.add(2)
        assert calls == []
        assert len(buffer) == 2

    def test_add_reaching_capacity_auto_flushes_once(self):
        calls = []
        buffer = InMemoryClusterStorageBuffer(capacity=3, flush_callback=lambda items: calls.append(items))
        buffer.add(1)
        buffer.add(2)
        buffer.add(3)
        assert calls == [[1, 2, 3]]
        assert len(buffer) == 0

    def test_add_returns_none_when_not_flushing(self):
        buffer = InMemoryClusterStorageBuffer(capacity=2, flush_callback=lambda items: "flushed")
        assert buffer.add(1) is None


class TestFlush:

    def test_manual_flush_of_partial_buffer(self):
        calls = []

        def flush_callback(items):
            calls.append(items)
            return items

        buffer = InMemoryClusterStorageBuffer(capacity=10, flush_callback=flush_callback)
        buffer.add("a")
        buffer.add("b")
        result = buffer.flush()
        assert calls == [["a", "b"]]
        assert result == calls[0]
        assert len(buffer) == 0

    def test_flush_on_empty_buffer_returns_none_and_skips_callback(self):
        called = False

        def flush_callback(items):
            nonlocal called
            called = True
            return items

        buffer = InMemoryClusterStorageBuffer(capacity=3, flush_callback=flush_callback)
        assert buffer.flush() is None
        assert called is False

    def test_flush_returns_callback_result(self):
        buffer = InMemoryClusterStorageBuffer(capacity=3, flush_callback=lambda items: [id(i) for i in items])
        buffer.add("x")
        result = buffer.flush()
        assert result == [id("x")]


class TestLen:

    def test_len_tracks_additions_and_flushes(self):
        buffer = InMemoryClusterStorageBuffer(capacity=5, flush_callback=lambda items: items)
        assert len(buffer) == 0
        buffer.add(1)
        buffer.add(2)
        assert len(buffer) == 2
        buffer.flush()
        assert len(buffer) == 0


class TestIteration:

    def test_iter_yields_buffered_items_in_order(self):
        buffer = InMemoryClusterStorageBuffer(capacity=5, flush_callback=lambda items: items)
        buffer.add(1)
        buffer.add(2)
        buffer.add(3)
        assert list(buffer) == [1, 2, 3]

    def test_iter_does_not_mutate_buffer(self):
        buffer = InMemoryClusterStorageBuffer(capacity=5, flush_callback=lambda items: items)
        buffer.add(1)
        buffer.add(2)
        list(buffer)
        assert len(buffer) == 2
        assert list(buffer) == [1, 2]

    def test_iter_on_empty_buffer(self):
        buffer = InMemoryClusterStorageBuffer(capacity=5, flush_callback=lambda items: items)
        assert list(buffer) == []


class TestContextManager:

    def test_normal_exit_flushes_partial_batch(self):
        calls = []
        with InMemoryClusterStorageBuffer(capacity=10, flush_callback=lambda items: calls.append(items)) as buffer:
            buffer.add(1)
            buffer.add(2)
        assert calls == [[1, 2]]

    def test_exception_exit_does_not_flush(self):
        calls = []
        with pytest.raises(RuntimeError):
            with InMemoryClusterStorageBuffer(capacity=10, flush_callback=lambda items: calls.append(items)) as buffer:
                buffer.add(1)
                raise RuntimeError("boom")
        assert calls == []

    def test_context_manager_returns_self(self):
        buffer = InMemoryClusterStorageBuffer(capacity=10, flush_callback=lambda items: items)
        with buffer as entered:
            assert entered is buffer


class TestGenericReuse:
    """Proves the buffer isn't hardcoded to the Cluster domain."""

    def test_reusable_with_plain_int_items(self):
        calls = []
        buffer: InMemoryClusterStorageBuffer[int] = InMemoryClusterStorageBuffer(
            capacity=2, flush_callback=lambda items: calls.append(sum(items))
        )
        buffer.add(10)
        buffer.add(20)
        assert calls == [30]

    def test_reusable_with_dict_items_and_different_return_type(self):
        def flush_callback(items):
            return {"count": len(items)}

        buffer = InMemoryClusterStorageBuffer(capacity=2, flush_callback=flush_callback)
        buffer.add({"id": 1})
        result = buffer.flush()
        assert result == {"count": 1}
