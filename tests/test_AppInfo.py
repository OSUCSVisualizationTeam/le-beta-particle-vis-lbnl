"""Smoke tests for AppInfo — pure Python, no QApplication required."""

from le_beta_vis.common import APP_VERSION, APP_NAME


class TestAppInfo:
    def test_version_is_nonempty_string(self) -> None:
        assert isinstance(APP_VERSION, str)
        assert len(APP_VERSION) > 0

    def test_version_is_not_fallback(self) -> None:
        assert APP_VERSION != "0.0.0"

    def test_app_name_is_nonempty(self) -> None:
        assert isinstance(APP_NAME, str)
        assert len(APP_NAME) > 0
