# ClassifierService Contract & Gap Issue Draft

> **Note:** The original contract proposal below is preserved. The "Follow-up Issue" section at the top is a draft for a new GitHub issue to address gaps left in the #153 implementation. Review with Troy before creating.

---

## Follow-up Issue Draft

**Title:** Classification pipeline gaps: MockClassifierService async, common exports, ZMQBasedClassifierService wiring

**Labels:** backend, classifier, technical-debt

**Body:**

### Context

Issue #153 (`RawClusterClassificationDialog`) was implemented with `MockClassifierService` as a stand-in. Three known gaps were left as `TODO(#XXX)` comments in the code and need to be resolved before the feature is production-ready.

### Gap 1 — `MockClassifierService` threading path is commented out

**File:** `src/le_beta_vis/common/MockClassifierService.py:31–44`

The `threading.Thread` block that makes `classify_cluster()` truly async is commented out. Currently it executes synchronously on the calling thread. This is safe inside `RawClusterClassificationViewModel._run_classification()` because the ViewModel already wraps calls in a `daemon=True` thread, but it violates the `ClassifierService` contract ("callbacks fire from a background thread"). If `MockClassifierService` is ever used outside the ViewModel's wrapping thread, it will block the caller.

**Work:**
- Uncomment the `threading.Thread` block in `classify_cluster()`
- Ensure `on_error` is wired correctly in the thread target
- Update / add unit tests to verify `on_complete` fires off the calling thread

### Gap 2 — `ClusteredEventInfo → ClassificationRequestCluster` conversion is index-keyed

**File:** `src/le_beta_vis/frontend/viewmodels/RawClusterClassificationViewModel.py` (`_to_request_clusters`)

`ClassificationRequestCluster.cluster_id` is set to the list index because `ClusteredEventInfo` has no persistent ID. This is safe as long as `ClassificationBatchResult.results` is ordered to match the input list, which the contract guarantees. However:

- If a future `ClassifierService` implementation does not preserve ordering, correlation silently breaks.
- Edge cases are unaudited: zero-pixel clusters, clusters with `data=None` (though raw clusters always have data populated by the extractor).

**Work:**
- Audit the conversion for edge cases (zero-pixel cluster, non-contiguous data shapes)
- Add a guard or assertion that `data` is not None before calling `.tolist()`
- Consider adding ordering verification (e.g. assert `result.cluster_id == index` after each model call)

### Gap 3 — `ZMQBasedClassifierService` is not wired through `ServicesManager`

**Files:**
- `src/le_beta_vis/backend/ZMQBasedClassifierServer.py` (and the duplicate `ZMQBasedClassifierService.py`)
- `src/le_beta_vis/frontend/views/raw_data_view/RawDataView.py` (`_onClassifyRequested`)

`ZMQBasedClassifierServer` is never instantiated — `ServicesManager` starts only `EPSRunner` and `PollingRunner`. The classification dialog currently uses `MockClassifierService()` via a `TODO(#XXX)` comment.

Additionally, `ZMQBasedClassifierServer.py` and `ZMQBasedClassifierService.py` appear to be identical duplicates — one should be removed.

**Work:**
- Decide whether the server should run in-process (via `ServicesManager`) or out-of-process
- Add a `ClassifierRunner` (or equivalent) to `ServicesManager` that starts `ZMQBasedClassifierServer`
- Replace `MockClassifierService()` in `RawDataView._onClassifyRequested` with the production service, injected via the existing dependency chain
- Remove the duplicate file (`ZMQBasedClassifierService.py` vs `ZMQBasedClassifierServer.py`)

### Acceptance Criteria

- [ ] `MockClassifierService.classify_cluster()` fires `on_complete` from a background thread (not the calling thread) — still open, untouched by #54 (LBNLTritiumClassifierService implements its own correct async path independently, so this stopped being a blocker for #54, but the mock itself is unfixed)
- [ ] `_to_request_clusters()` guards against `None` data and documents the index-as-id invariant — still open; #54's `FileProcessing._classify_clusters` uses the same index-as-id pattern without adding the suggested guard/assertion
- [x] ~~`ZMQBasedClassifierServer` starts as part of normal application launch~~ **Decided differently in #54:** in-process wiring instead of a ZMQ server/client split — see `wiki/Architecture-Decision-Records-(ADRs).md` ADR-0013 and `mock-classifier-todos.md`. `ZMQBasedClassifierServer` remains unstarted/unused; revisit only if classification genuinely needs to run in a separate process.
- [x] `RawDataView._onClassifyRequested` uses a production `ClassifierService` (`LBNLTritiumClassifierService` when `classifier:service_backend` is `lbnl_tritium`), not a hardcoded `MockClassifierService` — done via `create_classifier_service`, in-process (not `ZMQBasedClassifierService`, per the decision above)
- [ ] Duplicate server file removed — out of scope for #54, still open

---

## Original Contract Proposal

## Data Types

```python
@dataclass
class ClassificationScore:
    particle_type: ParticleType
    confidence: float


@dataclass
class ClassificationResult:
    cluster_id: int
    model: ClassifierModel
    score: Optional[ClassificationScore]  # None if classification failed for this cluster


@dataclass
class ClassificationBatchResult:
    results: list[ClassificationResult]  # order matches input clusters
    total: int
    failed: int


class ClassifierModel(str, Enum):
    CNN = "cnn"
    NRG = "nrg"
    BDT = "bdt"
```

## Callback Types

```python
ErrorCallback = Callable[[Exception], None]
CompletionCallback = Callable[[ClassificationBatchResult], None]
```

- `on_complete` — fires once when the full batch is done; results are ordered to match the input `clusters` list.
- `on_error` — fires on fatal / transport-level failures (e.g. ZMQ down, service unavailable). Per-cluster failures are represented as `score=None` in the result and counted in `ClassificationBatchResult.failed`; they do not trigger `on_error`.

## Abstract Base Class

```python
class ClassifierService(ABC):
    """
    All classify_* methods are asynchronous. Callbacks fire from a background
    thread — callers that update Qt state must dispatch via Signal or
    QMetaObject.invokeMethod. Cluster.data must be hydrated by the caller
    before passing clusters to any classify_* method.
    """

    @abstractmethod
    def classify_cnn(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    @abstractmethod
    def classify_nrg(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...

    @abstractmethod
    def classify_bdt(
        self,
        clusters: list[Cluster],
        on_complete: CompletionCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None: ...
```

## Design Decisions

- **One method per classifier** — each classifier method has an independent signature. Future classifiers for different particle families (e.g. muons) may require different input features and can be added as new methods without breaking existing ones.
- **No `classify_all`** — callers invoke individual methods; coordination across models is the caller's responsibility.
- **`Cluster.data` hydration is the caller's responsibility** — the service does not own `ThumbnailLoaderService`. Callers (e.g. `ClusteredEventWidget`, file processing pipeline) must pre-fetch pixel data before calling any `classify_*` method.
- **Ordered batch results** — `ClassificationBatchResult.results` is guaranteed to match the order of the input `clusters` list, making index-based correlation safe.
- **Per-cluster failure isolation** — a failed cluster produces `score=None` and increments `failed`; it does not abort the batch or trigger `on_error`.
- **`ClassifierModel` as `str` enum** — allows safe dispatch in the inspector without stringly-typed comparisons; new models are added as enum members.
