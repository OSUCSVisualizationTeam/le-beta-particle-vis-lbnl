"""Tests for LicenseDocuments' relative-link rewriting — pure Python, no Qt."""

from le_beta_vis.common.LicenseDocuments import _rewrite_relative_links

_BASE = "https://github.com/OSUCSVisualizationTeam/le-beta-particle-vis-lbnl/blob/main/"


class TestRewriteRelativeLinks:
    def test_relative_path_is_rewritten(self) -> None:
        result = _rewrite_relative_links("[a](pyproject.toml)", _BASE)
        assert result == f"[a]({_BASE}pyproject.toml)"

    def test_nested_relative_path_is_rewritten(self) -> None:
        text = "[x](src/le_beta_vis/export/fonts/LICENSE_DEJAVU)"
        result = _rewrite_relative_links(text, _BASE)
        assert result == f"[x]({_BASE}src/le_beta_vis/export/fonts/LICENSE_DEJAVU)"

    def test_absolute_https_link_is_untouched(self) -> None:
        text = "[a](https://dejavu-fonts.github.io/)"
        assert _rewrite_relative_links(text, _BASE) == text

    def test_anchor_link_is_untouched(self) -> None:
        text = "[a](#section)"
        assert _rewrite_relative_links(text, _BASE) == text

    def test_mailto_link_is_untouched(self) -> None:
        text = "[a](mailto:foo@example.com)"
        assert _rewrite_relative_links(text, _BASE) == text

    def test_text_without_links_is_untouched(self) -> None:
        text = "Plain text, no links here."
        assert _rewrite_relative_links(text, _BASE) == text
