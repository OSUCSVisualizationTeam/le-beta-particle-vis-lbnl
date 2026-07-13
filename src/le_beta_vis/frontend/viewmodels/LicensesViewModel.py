"""ViewModel for the About dialog's Licenses tab — pure Python, no Qt dependencies."""

from le_beta_vis.common import get_license_text, get_third_party_notices_text


class LicensesViewModel:
    """Exposes raw license and third-party notices text for display."""

    @property
    def license_text(self) -> str:
        """Return the raw text of the project's LICENSE file."""
        return get_license_text()

    @property
    def third_party_notices_text(self) -> str:
        """Return the raw text of the project's THIRD_PARTY_NOTICES.md file."""
        return get_third_party_notices_text()
