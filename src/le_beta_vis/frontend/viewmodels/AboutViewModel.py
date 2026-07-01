"""ViewModel for the About dialog — pure Python, no Qt dependencies."""

from le_beta_vis.common import (
    APP_NAME,
    APP_REPOSITORY_BLOB_BASE_URL,
    APP_REPOSITORY_URL,
    APP_VERSION,
)


class AboutViewModel:
    """Exposes read-only application metadata for the About dialog."""

    @property
    def app_name(self) -> str:
        """Return the application display name."""
        return APP_NAME

    @property
    def version(self) -> str:
        """Return the raw version string."""
        return APP_VERSION

    @property
    def authors(self) -> str:
        """Return the application authors."""
        return "Juan Guerrero & Troy Rice"

    @property
    def year(self) -> str:
        """Return the copyright year."""
        return "2026"

    @property
    def organization(self) -> str:
        """Return the sponsoring university."""
        return "Oregon State University"

    @property
    def developed_for(self) -> str:
        """Return the target laboratory."""
        return "Lawrence Berkeley National Laboratory"

    @property
    def repository_url(self) -> str:
        """Return the source repository URL."""
        return APP_REPOSITORY_URL

    @property
    def repository_blob_base_url(self) -> str:
        """Return the base URL for viewing repo files at the default branch."""
        return APP_REPOSITORY_BLOB_BASE_URL

    @property
    def license_url(self) -> str:
        """Return the URL of the LICENSE file in the source repository."""
        return f"{self.repository_blob_base_url}LICENSE"

    def formatted_version(self) -> str:
        """Return a human-readable version label."""
        return f"Version {self.version}"

    def copyright_line(self) -> str:
        """Return a one-line copyright notice."""
        return f"\u00a9 {self.year} {self.organization}"
