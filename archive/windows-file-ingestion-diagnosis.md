# Windows File Ingestion Hang — Diagnosis Report

**Branch:** `fix/windows_zmq_fallbak`
**Reported by:** Juan Guerrero
**Diagnosed on:** Windows 11, 2026-07-16
**Status:** Root cause confirmed via live reproduction. Not yet fixed.

## TL;DR

`process_file()` in `src/le_beta_vis/backend/FileProcessing.py` never finishes
processing a FITS file dropped into the polling folder on Windows, because
`watchdog` reports the file as "created" before Windows has finished writing
it to disk. `astropy.io.fits.open()` opens the half-written file, and
something downstream deadlocks permanently trying to read past the data that
actually exists. The single ingestion worker thread hangs forever on the
first file, so every file after it just sits unprocessed in the queue with
no crash, no exception, and no further log output. This is Windows-specific
and unrelated to the Windows ZMQ `ipc://` fallback work also on this branch.

## Root cause

**File:** `src/le_beta_vis/backend/FileProcessing.py:23-41`
**File:** `src/le_beta_vis/backend/InitializePolling.py:76-97`

1. `InitializePolling.EventHandler.on_created()` is wired to `watchdog`'s
   `Observer`, which on Windows uses `ReadDirectoryChangesW` under the hood.
   That API reports a file as "created" the instant its directory entry
   appears — **not** when the writer finishes writing and closes the file.
   For a large copy (the demo file is ~28 MB), this leaves a real window
   where the file exists on disk but is still partially written.

2. `on_created` pushes the path onto `PollingThread.file_queue` immediately.
   `file_uploaded()` (the single dedicated consumer thread for this queue)
   pulls it off and calls `process_file()` right away — no check anywhere
   in this path waits for the file to finish writing or become stable.

3. `process_file()` (`FileProcessing.py:30`) calls
   `CCDCaptureModel.load(file)` → `astropy.io.fits.open(fitsFile)` on the
   still-writing file. Astropy notices the mismatch and logs a *warning*
   (not an exception):
   ```
   WARNING: File may have been truncated: actual file length (9306112)
   is smaller than the expected size (14112000) [astropy.io.fits.file]
   ```
   It does not raise — it returns an `HDUList` that believes more data
   exists than is currently on disk.

4. Somewhere downstream of that (most likely inside `hdu.data.min()` /
   `hdu.data.max()` in `CCDCaptureModel.Info.fromHDU`, while astropy tries
   to lazily read data past what's actually available), execution
   **deadlocks permanently**. This was confirmed, not assumed — see
   "What I did to troubleshoot" below. It does not recover even after the
   file finishes copying and reaches its full size on disk; the astropy/numpy
   read appears to be stuck against a stale memory-map or lock made against
   the file object opened while it was still short.

5. Because `file_uploaded()` processes the queue **serially in one thread**,
   this permanent hang on the first file blocks that thread forever. Every
   subsequent file dropped into the folder is enqueued but never
   dequeued/processed — no error, no timeout, nothing. This matches the
   reported symptom exactly: "process_file is not processing the files."

### Why this doesn't happen on Linux/macOS

`inotify` (Linux) and `FSEvents` (macOS) give `watchdog` a much closer
approximation of "the write is actually done" for typical demo-file-sized
copies, so the race window this depends on essentially doesn't open in
practice on those platforms. There is currently **no explicit file-stability
check anywhere in the ingestion pipeline** (e.g. poll file size until it
stops changing, or attempt an exclusive open before handing the path to
`process_file`) — the code has simply never needed one on the platforms it's
been exercised on.

### A related (but not root-cause) fragility worth fixing alongside this

`FileProcessing.py:30` — `capture = CCDCaptureModel.load(file)` — sits
**outside** the `try/except` that starts at line 34. Even in a world where
astropy raised cleanly instead of hanging, that exception would not be
caught by `process_file`'s own handler; it would propagate up to
`InitializePolling.file_uploaded`'s broad `except Exception`, which is a
different place than where every other failure in this function gets
logged. Worth tightening while this area is being touched.

## What the fix probably looks like

The core need is a **file-stability guard between "watchdog says a file
exists" and "process_file gets called on it."** A few ways this could be
shaped — the right one probably depends on tools/conventions the Linux-side
instance has that I don't have access to here (e.g. if there's an existing
debounce/retry utility elsewhere in the codebase worth reusing):

- **Poll-until-stable before enqueueing or before dequeueing.** Check the
  file size (and/or last-modified time) twice with a short delay between
  reads; only proceed once it's unchanged. This is the standard pattern for
  watcher-based ingestion pipelines and would fix this on Windows without
  changing behavior on Linux/macOS (where the file is already stable by the
  time the event fires, so the check would pass instantly).
- **Attempt an exclusive open as the stability signal**, since on Windows a
  process still writing to a file typically holds a lock that a second
  exclusive `open()` will fail against. Retry with backoff until the open
  succeeds, then hand the path to `process_file`. This is arguably a more
  reliable signal on Windows than a size check.
- **Defense in depth, independent of the above:** don't let a single bad or
  slow file take down the entire ingestion pipeline forever. Right now
  `file_uploaded` is a single-threaded consumer with no timeout around
  `process_file`. Even after adding a stability check, a corrupted file, an
  antivirus lock, or a future edge case could still wedge it. Worth
  considering either a timeout around the processing call (e.g. run it in a
  short-lived thread/future and give up after N seconds with a logged error)
  or moving `CCDCaptureModel.load` inside `process_file`'s existing
  try/except so at least clean exceptions surface where they're supposed to.
- Whatever shape the fix takes, it should be validated with a **real**
  filesystem/watchdog test, not a mocked one — the existing
  `tests/test_InitializePolling.py` mocks out `Observer` entirely, so it
  cannot regression-test this. A live test writing a real multi-MB file
  slowly (e.g. in chunks with sleeps) into a `tmp_path` and asserting
  `process_file` is only invoked once the file is complete would actually
  cover this.

## What I did to troubleshoot (and preserved logging)

1. Read `FileProcessing.py` and `InitializePolling.py`, and diffed the
   working tree against `HEAD` to rule out the user's own uncommitted edits
   as the cause.
2. Investigated the Windows ZMQ `ipc://` fallback machinery on this branch
   (`IPCFallbackSupport.py`, `StartupIPCBindRegistry.py`, `app.py`) since it
   was the most recent Windows-related change. Confirmed via the live
   `%APPDATA%\mlccd_viz.yaml` that this migration had **already run
   successfully** on this machine (`eps:fits_ipc` / `eps:cluster_ipc` were
   already `tcp://127.0.0.1:...`) — so it is not the active cause here,
   though it's a real, separate, confirmed-by-design quirk (`app.py:146`
   calls `sys.exit(0)` right after the fallback dialog closes, requiring a
   manual relaunch — intentional per the dialog's own UI text, not a bug).
3. Verified the MySQL side end-to-end was not the problem: confirmed the
   `mysql-database` container was up, that `root`/`root` authenticates
   successfully from inside the container, and — more importantly — that
   `mysql.connector.connect(host="localhost", user="root", password="root",
   database="lbnlfits")` succeeds from the Windows host process itself
   (same call `EventPersistenceService.db_connect()` makes).
4. **Reproduced the actual reported symptom directly**, following the
   user's exact repro steps: launched `uv run -vvvv run_app.py`, confirmed
   via console log that no IPC fallback dialog was needed and EPS/Polling
   started cleanly, then copied
   `archive/cluster_demonstration/fits_files/Oct6-2022-Exposure-With-Tritium.fits`
   into `C:\Users\Juan\Downloads\lbnlfits`. Captured the full console log
   (`logging.basicConfig(level=logging.DEBUG, ...)` in `app.py` sends
   everything to stdout). Relevant excerpt:

   ```
   20:18:52 INFO   le_beta_vis.common.IPCFallbackSupport — IPC fallback probe skipped: all startup endpoints already use tcp://.
   20:18:52 INFO   le_beta_vis.backend.EPSRunner — EPS has started.
   20:18:52 INFO   le_beta_vis.backend.PollingRunner — File Ingest has started.
   20:18:52 DEBUG  le_beta_vis.common.StartupIPCBindRegistry — bind_tracked_ipc_socket: bound eps:fits_ipc -> tcp://127.0.0.1:64963
   20:18:52 DEBUG  le_beta_vis.common.StartupIPCBindRegistry — bind_tracked_ipc_socket: bound eps:cluster_ipc -> tcp://127.0.0.1:64964
   20:18:52 DEBUG  le_beta_vis.common.StartupIPCBindRegistry — bind_tracked_ipc_socket: bound eps:command_ipc -> tcp://127.0.0.1:64965
   20:19:11 INFO   le_beta_vis.backend.InitializePolling — New file creation polled: C:\Users\Juan\Downloads\lbnlfits\Oct6-2022-Exposure-With-Tritium.fits
   20:19:11 INFO   le_beta_vis.backend.FileProcessing — Processing C:\Users\Juan\Downloads\lbnlfits\Oct6-2022-Exposure-With-Tritium.fits
   WARNING: File may have been truncated: actual file length (9306112) is smaller than the expected size (14112000) [astropy.io.fits.file]
   20:19:11 WARNING astropy — File may have been truncated: actual file length (9306112) is smaller than the expected size (14112000)
   ```

   No further log lines were ever produced after this point — not the
   `logger.info(f"Got CCD capture {capture}")` line at `FileProcessing.py:31`,
   nor any exception, nor anything else.

5. To rule out "just slow" vs. "actually stuck," checked the app process's
   accumulated CPU time twice, ~15 seconds apart, well after the file copy
   had finished and the file had reached its full 28,224,000-byte size on
   disk (confirmed via directory listing):

   ```
   Id     CPU   (first check)
   46436  3.47
   Id     CPU   (second check, ~4s later)
   46436  3.47
   ```

   CPU time was completely flat across both checks — the process was
   idle/blocked, not computing. This is what confirms "deadlock," not
   "large file, give it a moment."

6. Cleaned up after the repro: killed the test app process, deleted the
   copied test FITS file from `C:\Users\Juan\Downloads\lbnlfits`, and
   confirmed no stray `python.exe` processes were left running.

## Additional context (not the bug, but explains why it was never caught)

- There is no Windows job anywhere in `.github/workflows/` — CI only runs
  on `ubuntu-latest`. This pipeline has never been exercised on Windows in
  CI, ever.
- The one existing test file for this code path,
  `tests/test_InitializePolling.py`, mocks out `watchdog.Observer` entirely
  and uses a Unix-style `/tmp` fixture path — it cannot exercise real
  filesystem event timing on any platform, let alone Windows's.
- Git history shows the entire ingestion/EPS backend was authored by one
  contributor (`troyr01`/Troy Rice) starting February 2026, and the only
  Windows-specific runtime fix in the repo's history is the `ipc://`
  fallback work on this same branch, authored today. No prior commit ever
  addressed Windows-specific ingestion or ZMQ behavior.
