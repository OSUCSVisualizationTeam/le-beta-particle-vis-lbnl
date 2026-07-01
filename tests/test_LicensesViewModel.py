"""Tests for LicensesViewModel — pure Python, no QApplication required."""

from le_beta_vis.common.LicenseDocuments import _resolve_repo_root_file
from le_beta_vis.frontend.viewmodels.LicensesViewModel import LicensesViewModel


class TestLicensesViewModel:
    def setup_method(self) -> None:
        self.vm = LicensesViewModel()

    def test_license_text_contains_mit(self) -> None:
        assert "MIT License" in self.vm.license_text

    def test_license_text_contains_lbnl_copyright(self) -> None:
        assert "Lawrence Berkeley National Laboratory" in self.vm.license_text

    def test_third_party_notices_text_contains_header(self) -> None:
        assert "Third-Party Notices" in self.vm.third_party_notices_text

    def test_third_party_notices_relative_links_are_absolute(self) -> None:
        text = self.vm.third_party_notices_text
        assert "](pyproject.toml)" not in text
        assert (
            "](https://github.com/OSUCSVisualizationTeam/"
            "le-beta-particle-vis-lbnl/blob/main/pyproject.toml)" in text
        )

    def test_license_file_exists_on_disk(self) -> None:
        assert _resolve_repo_root_file("LICENSE").exists()

    def test_third_party_notices_file_exists_on_disk(self) -> None:
        assert _resolve_repo_root_file("THIRD_PARTY_NOTICES.md").exists()
