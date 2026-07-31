"""Live/manual-verification tests for the Windows ipc:// fallback (issue #204).

Unlike the rest of the suite, these tests touch real sockets, real files,
and (for the dialog test) a real ``QApplication`` — they are not mocked.
Skipped by default; set ``LBNLVIS_LIVE_TESTS=1`` to run them:

    LBNLVIS_LIVE_TESTS=1 uv run pytest tests/test_live_ipc_fallback.py -v

This is also the reusable convention for any future live/manual-verification
test: a ``tests/test_live_*.py`` file gated by this same env var.

NOTE: ``test_live_dialog_renders_without_error`` requires a display server
(QApplication). It is excluded from headless CI via --ignore in
python-package-uv.yml, per the project's convention for Qt-bug-fix
integration tests (issue #204 is the recorded bug).
"""

import os
import sys

import pytest

from le_beta_vis.common.IPCFallbackSupport import is_ipc_bind_supported
from le_beta_vis.common.StartupIPCBindRegistry import STARTUP_IPC_BIND_KEYS
from le_beta_vis.common.YAMLBackedConfigurationService import (
    YAMLBackedConfigurationService,
)
from le_beta_vis.frontend.viewmodels.IPCFallbackViewModel import IPCFallbackViewModel

pytestmark = pytest.mark.skipif(
    os.environ.get("LBNLVIS_LIVE_TESTS") != "1",
    reason="Live/manual-verification test; set LBNLVIS_LIVE_TESTS=1 to run.",
)


def test_live_probe_matches_platform_expectation():
    """Tripwire, not just a repro check.

    ``ipc://`` binds are expected to fail on Windows and succeed
    everywhere else, per issue #204. If this assertion ever flips to
    ``True`` on Windows, it means a pyzmq/libzmq release fixed native
    Windows ``ipc://`` support — the fallback dialog and this whole
    feature should be revisited, not just this test.
    """
    import platform

    supported = is_ipc_bind_supported()
    if platform.system() == "Windows":
        assert supported is False, (
            "ipc:// binds now succeed on Windows — pyzmq/libzmq may have "
            "fixed native Windows ipc:// support. Revisit the IPC fallback "
            "dialog (issue #204) before removing it."
        )
    else:
        assert supported is True


def test_live_fallback_roundtrip_with_real_config(tmp_path):
    """Exercises the full probe -> save -> persisted round trip against
    real file I/O, with no mocking. Not Windows-specific — it doesn't
    depend on the probe's platform-specific result, only on the
    ViewModel/config-service persistence path."""
    scratch_yaml = tmp_path / "mlccd_viz_live_test.yaml"
    config = YAMLBackedConfigurationService(yaml_path=scratch_yaml)

    for key in STARTUP_IPC_BIND_KEYS:
        assert str(config.get(key)).startswith("ipc://")

    vm = IPCFallbackViewModel(config)
    assert vm.save() is True

    reloaded = YAMLBackedConfigurationService(yaml_path=scratch_yaml)
    for key in STARTUP_IPC_BIND_KEYS:
        assert str(reloaded.get(key)).startswith("tcp://")


def test_live_dialog_renders_without_error(tmp_path):
    """Smoke test: constructs the real dialog and confirms it renders and
    can be dismissed without raising. Requires a display server."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from le_beta_vis.frontend.widgets.IPCFallbackDialogView import (
        IPCFallbackDialogView,
    )

    app = QApplication.instance() or QApplication(sys.argv)

    scratch_yaml = tmp_path / "mlccd_viz_live_dialog_test.yaml"
    config = YAMLBackedConfigurationService(yaml_path=scratch_yaml)
    vm = IPCFallbackViewModel(config)
    dialog = IPCFallbackDialogView(vm)

    # dialog.closeEvent() intentionally ignores close requests, so a
    # timer-driven .close() would hang; accept()/reject() bypass
    # closeEvent entirely via Qt's done().
    QTimer.singleShot(200, dialog.accept)
    dialog.exec()

    del app
