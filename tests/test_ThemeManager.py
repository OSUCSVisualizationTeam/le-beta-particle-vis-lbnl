from pathlib import Path

from le_beta_vis.common.ThemeManager import ColorScheme, ThemeManager


def test_resolve_color_scheme_override_wins_over_provider():
    manager = ThemeManager(
        color_scheme_provider=lambda: ColorScheme.LIGHT,
        override=ColorScheme.DARK,
    )
    assert manager.resolve_color_scheme() == ColorScheme.DARK


def test_resolve_color_scheme_uses_provider_when_no_override():
    manager = ThemeManager(color_scheme_provider=lambda: ColorScheme.LIGHT)
    assert manager.resolve_color_scheme() == ColorScheme.LIGHT


def test_resolve_color_scheme_unknown_falls_back_to_dark():
    manager = ThemeManager(color_scheme_provider=lambda: ColorScheme.UNKNOWN)
    assert manager.resolve_color_scheme() == ColorScheme.DARK


def test_resolve_color_scheme_provider_exception_falls_back_to_dark():
    def _raise():
        raise RuntimeError("no QApplication")

    manager = ThemeManager(color_scheme_provider=_raise)
    assert manager.resolve_color_scheme() == ColorScheme.DARK


def test_stylesheet_paths_dark(tmp_path: Path):
    qss_dir = tmp_path
    (qss_dir / "dark").mkdir()
    (qss_dir / "dark" / "core.qss").write_text("dark-core")
    (qss_dir / "dark" / "controls.qss").write_text("dark-controls")
    (qss_dir / "base.qss").write_text("base")

    manager = ThemeManager(color_scheme_provider=lambda: ColorScheme.DARK)
    paths = manager.stylesheet_paths(qss_dir)

    assert paths == [
        qss_dir / "base.qss",
        qss_dir / "dark" / "controls.qss",
        qss_dir / "dark" / "core.qss",
    ]


def test_stylesheet_paths_light(tmp_path: Path):
    qss_dir = tmp_path
    (qss_dir / "light").mkdir()
    (qss_dir / "light" / "core.qss").write_text("light-core")
    (qss_dir / "base.qss").write_text("base")

    manager = ThemeManager(color_scheme_provider=lambda: ColorScheme.LIGHT)
    paths = manager.stylesheet_paths(qss_dir)

    assert paths == [qss_dir / "base.qss", qss_dir / "light" / "core.qss"]


def test_load_stylesheet_concatenates_files_in_order(tmp_path: Path):
    qss_dir = tmp_path
    (qss_dir / "dark").mkdir()
    (qss_dir / "base.qss").write_text("BASE")
    (qss_dir / "dark" / "core.qss").write_text("CORE")

    manager = ThemeManager(color_scheme_provider=lambda: ColorScheme.DARK)
    result = manager.load_stylesheet(qss_dir)

    assert result == "BASE\nCORE"


def test_load_stylesheet_skips_missing_files(tmp_path: Path):
    qss_dir = tmp_path
    (qss_dir / "dark").mkdir()
    (qss_dir / "dark" / "core.qss").write_text("CORE")
    # base.qss intentionally not created

    manager = ThemeManager(color_scheme_provider=lambda: ColorScheme.DARK)
    result = manager.load_stylesheet(qss_dir)

    assert result == "CORE"
