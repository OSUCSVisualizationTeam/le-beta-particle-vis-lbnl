# Mock Classifier — Pending Items (from #73)

Issue #73 ("Mock Pipeline Functionality for Classifying Clusters") is implemented and
closed. Two gaps were found during review that don't block #73's stated deliverables but
should be decided on before/alongside #54 (real model integration).

**Update (2026-08-19, #54 landed):** Gap 2 is now decided — in-process wiring, not a ZMQ
client wrapper (see below). Gap 1 is unchanged; it's specific to `MockClassifierService`
itself and doesn't block #54, since the real `LBNLTritiumClassifierService` (issue #54,
`wiki/Front-Design-Tritium-Classification.md`) implements its own genuinely-async
`threading.Thread` path correctly and doesn't share this limitation.

## 1. Mock's async delay is disabled

`MockClassifierService.classify_cluster()` (`src/le_beta_vis/common/MockClassifierService.py`)
has the real async path commented out:

```python
self.random_classification(clusters, on_complete, model, on_error)

# For asynchronous use:
# def _run() -> None:
#     ...
# threading.Thread(target=_run, daemon=True).start()
```

It currently calls `random_classification()` synchronously, blocking the caller's thread
on `time.sleep(.2)`. Issue #73 explicitly asked for a simulated delay "so callers exercise
the asynchronous path rather than getting an instant synchronous-looking result."

This is currently masked because `RawClusterClassificationViewModel._run_classification()`
(`src/le_beta_vis/frontend/viewmodels/RawClusterClassificationViewModel.py:114`) already
runs inside its own daemon thread, so nothing breaks today. There's a
`TODO(#XXX)` at line 132 acknowledging this is a known shortcut, not a resolved decision.

**Decision needed:** re-enable the threaded path in the mock (correctness bar per
CLAUDE.md's async-backend-call rule), or formally decide callers are always expected to
self-thread and drop the async simulation from the mock's contract.

## 2. No ZMQ client half — only the server exists

Deliverable #3 in #73 asked for "a ZMQ transport layer so clients can reach the mock
service over ZMQ using the same `ClassifierService` interface."

What's built: `ZMQBasedClassifierServer` (`src/le_beta_vis/backend/ZMQBasedClassifierServer.py`)
— a REP-socket server that wraps a `ClassifierService` and exposes it over ZMQ.

What's missing: a REQ-socket client implementing `ClassifierService` for the frontend to
call. Today `RawDataView.py:255` instantiates `MockClassifierService()` directly,
in-process — classification never actually crosses ZMQ in the running app.

**Decided (#54):** in-process wiring. `RawDataView` and `InitializePolling.PollingThread`
each construct their own `ClassifierService` (`mock` or `lbnl_tritium`, via
`create_classifier_service`) directly in-process — no ZMQ client wrapper was built. Revisit
if/when the classifier genuinely needs to run in a separate process (e.g. GPU-equipped
worker box distinct from the ingestion machine); `ZMQBasedClassifierServer` is still unused
today.

## Related TODO markers in code (placeholder issue numbers)

- `src/le_beta_vis/frontend/viewmodels/RawClusterClassificationViewModel.py:132` — still open,
  unrelated to #54 (it's about `MockClassifierService`'s own synchronous behavior, Gap 1 above).
- ~~`src/le_beta_vis/frontend/views/raw_data_view/RawDataView.py:253`~~ — resolved by #54;
  `_onClassifyRequested` now uses a cached `ClassifierService` built via
  `create_classifier_service`, no `MockClassifierService()` hardcoding left.
