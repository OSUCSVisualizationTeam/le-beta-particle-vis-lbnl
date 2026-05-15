import sys
import os
import time

_t0 = time.perf_counter()
print("[startup]   0.0 ms  process entry", flush=True)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from le_beta_vis.app import main  # noqa: E402

_t1 = time.perf_counter()
print(f"[startup] {(_t1 - _t0) * 1000:6.1f} ms  app module imported (PySide6 + module-level code)", flush=True)

if __name__ == "__main__":
    main()
