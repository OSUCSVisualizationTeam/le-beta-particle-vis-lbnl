"""Tests for AboutViewModel — pure Python, no QApplication required."""

from le_beta_vis.frontend.viewmodels.AboutViewModel import AboutViewModel
from le_beta_vis.common import APP_REPOSITORY_URL, APP_VERSION


class TestAboutViewModel:
    def setup_method(self) -> None:
        self.vm = AboutViewModel()

    def test_app_name(self) -> None:
        assert self.vm.app_name == "LE Beta Particle Visualization"

    def test_version_matches_common(self) -> None:
        assert self.vm.version == APP_VERSION

    def test_authors(self) -> None:
        assert self.vm.authors == "Juan Guerrero & Troy Rice"

    def test_year(self) -> None:
        assert self.vm.year == "2026"

    def test_organization(self) -> None:
        assert self.vm.organization == "Oregon State University"

    def test_developed_for(self) -> None:
        assert self.vm.developed_for == "Lawrence Berkeley National Laboratory"

    def test_repository_url(self) -> None:
        assert "github.com" in self.vm.repository_url

    def test_repository_url_matches_common(self) -> None:
        assert self.vm.repository_url == APP_REPOSITORY_URL

    def test_repository_blob_base_url(self) -> None:
        assert self.vm.repository_blob_base_url == f"{APP_REPOSITORY_URL}/blob/main/"

    def test_license_url_points_at_license_file(self) -> None:
        assert self.vm.license_url == f"{APP_REPOSITORY_URL}/blob/main/LICENSE"

    def test_formatted_version_contains_version(self) -> None:
        result = self.vm.formatted_version()
        assert APP_VERSION in result
        assert result.startswith("Version ")

    def test_copyright_line_contains_year_and_org(self) -> None:
        result = self.vm.copyright_line()
        assert "2026" in result
        assert "Oregon State University" in result
        assert "\u00a9" in result
