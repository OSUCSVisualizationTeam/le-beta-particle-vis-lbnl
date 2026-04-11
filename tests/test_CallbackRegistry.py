"""Unit tests for CallbackRegistry."""

import threading

import pytest

from le_beta_vis.common.CallbackRegistry import CallbackRegistry


class TestRegisterAndUnregister:

    def test_register_returns_uuid(self):
        reg = CallbackRegistry()
        cb_id = reg.register("cluster.classified", lambda e: None)
        assert isinstance(cb_id, str)
        assert len(cb_id) == 32

    def test_register_rejects_empty_event_name(self):
        reg = CallbackRegistry()
        with pytest.raises(ValueError):
            reg.register("", lambda e: None)

    def test_register_rejects_non_callable(self):
        reg = CallbackRegistry()
        with pytest.raises(TypeError):
            reg.register("foo", "not-a-function")  # type: ignore[arg-type]

    def test_unregister_removes_callback(self):
        reg = CallbackRegistry()
        cb_id = reg.register("foo", lambda e: None)
        assert reg.unregister(cb_id) is True
        assert reg.count("foo") == 0

    def test_unregister_unknown_id_returns_false(self):
        reg = CallbackRegistry()
        assert reg.unregister("deadbeef") is False

    def test_unregister_all_removes_every_callback_for_name(self):
        reg = CallbackRegistry()
        reg.register("foo", lambda e: None)
        reg.register("foo", lambda e: None)
        reg.register("bar", lambda e: None)
        removed = reg.unregister_all("foo")
        assert removed == 2
        assert reg.count("foo") == 0
        assert reg.count("bar") == 1

    def test_unregister_all_unknown_name_returns_zero(self):
        reg = CallbackRegistry()
        assert reg.unregister_all("nothing") == 0


class TestSnapshots:

    def test_snapshot_single_returns_registration_order(self):
        reg = CallbackRegistry()
        order = []
        reg.register("foo", lambda e, i=0: order.append(i))
        reg.register("foo", lambda e, i=1: order.append(i))
        reg.register("foo", lambda e, i=2: order.append(i))
        cbs = reg.snapshot_single("foo")
        assert len(cbs) == 3
        for cb in cbs:
            cb(None)
        assert order == [0, 1, 2]

    def test_snapshot_single_excludes_batch_callbacks(self):
        reg = CallbackRegistry()
        reg.register("foo", lambda e: None, is_batch=False)
        reg.register("foo", lambda batch: None, is_batch=True)
        assert len(reg.snapshot_single("foo")) == 1
        assert len(reg.snapshot_batch("foo")) == 1

    def test_snapshot_unknown_name_returns_empty_list(self):
        reg = CallbackRegistry()
        assert reg.snapshot_single("nothing") == []
        assert reg.snapshot_batch("nothing") == []

    def test_event_names_returns_all_registered(self):
        reg = CallbackRegistry()
        reg.register("foo", lambda e: None)
        reg.register("bar", lambda e: None)
        assert set(reg.event_names()) == {"foo", "bar"}

    def test_clear_removes_everything(self):
        reg = CallbackRegistry()
        reg.register("foo", lambda e: None)
        reg.register("bar", lambda e: None)
        reg.clear()
        assert reg.count() == 0
        assert reg.event_names() == []


class TestThreadSafety:

    def test_concurrent_register_from_many_threads(self):
        reg = CallbackRegistry()
        n_threads = 16
        per_thread = 50
        start_gate = threading.Event()
        ids = []
        ids_lock = threading.Lock()

        def worker():
            start_gate.wait()
            for _ in range(per_thread):
                cb_id = reg.register("concurrent", lambda e: None)
                with ids_lock:
                    ids.append(cb_id)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        start_gate.set()
        for t in threads:
            t.join()

        assert reg.count("concurrent") == n_threads * per_thread
        assert len(set(ids)) == len(ids)  # all UUIDs unique

    def test_concurrent_register_and_unregister(self):
        reg = CallbackRegistry()
        stop = threading.Event()

        def registrar():
            while not stop.is_set():
                cb_id = reg.register("churn", lambda e: None)
                reg.unregister(cb_id)

        threads = [threading.Thread(target=registrar) for _ in range(4)]
        for t in threads:
            t.start()
        # Let them churn for a short while.
        import time
        time.sleep(0.1)
        stop.set()
        for t in threads:
            t.join()

        # After churn, count should be zero (every register paired with unregister).
        assert reg.count("churn") == 0
